import os
import uuid
from fastapi import FastAPI, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import yt_dlp

app = FastAPI()

# Katalog na tymczasowe pobrane pliki
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Ścieżka do pliku ciasteczek w Secret Files Rendera
COOKIES_FILE = "/etc/secrets/youtube_cookies.txt"

# Serwowanie plików statycznych (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

def cleanup_file(filepath: str):
    """Usuwa plik z dysku po wysłaniu go do użytkownika."""
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Błąd podczas usuwania pliku {filepath}: {e}")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.post("/api/download")
async def download_media(
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    format_type: str = Form(...)
):
    unique_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(DOWNLOAD_DIR, f"%(title)s_{unique_id}.%(ext)s")

    # Podstawowa konfiguracja yt-dlp
    ydl_opts = {
        'outtmpl': output_template,
        'noplaylist': True,  # Ignoruje całe playlisty/miksy i pobiera tylko 1 film
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web_creator', 'ios']
            }
        }
    }

    # Jeśli plik ciasteczek istnieje w Secret Files Rendera, podpinamy go do yt-dlp
    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        ydl_opts['cookiefile'] = COOKIES_FILE

    if format_type == "mp3":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        # Format MP4
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            # Pobranie poprawnego rozszerzenia po konwersji
            if format_type == "mp3":
                filename = os.path.splitext(filename)[0] + ".mp3"
            elif not filename.endswith(".mp4"):
                filename = os.path.splitext(filename)[0] + ".mp4"

        if not os.path.exists(filename):
            raise HTTPException(status_code=500, detail="Plik nie został przetworzony poprawnie.")

        # Czyszczenie pliku w tle po wysłaniu
        background_tasks.add_task(cleanup_file, filename)

        download_name = os.path.basename(filename)

        return FileResponse(
            path=filename,
            filename=download_name,
            media_type="application/octet-stream"
        )

    except Exception as e:
        print(f"Błąd pobierania: {e}")
        raise HTTPException(status_code=400, detail=f"Błąd podczas pobierania: {str(e)}")
