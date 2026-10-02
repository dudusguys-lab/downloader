import os
import uuid
import shutil
from fastapi import FastAPI, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import yt_dlp

app = FastAPI()

# Katalogi tymczasowe
DOWNLOAD_DIR = "/tmp/downloads"
WORKING_COOKIES_PATH = "/tmp/youtube_cookies.txt"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Ścieżka źródłowa z Secret Files Rendera
SECRET_COOKIES_PATH = "/etc/secrets/youtube_cookies.txt"

def setup_cookies():
    """Kopiuje ciasteczka do /tmp, aby yt-dlp miał pełne prawa zapisu."""
    if os.path.exists(SECRET_COOKIES_PATH) and os.path.getsize(SECRET_COOKIES_PATH) > 0:
        shutil.copy(SECRET_COOKIES_PATH, WORKING_COOKIES_PATH)
        return WORKING_COOKIES_PATH
    
    cookies_env = os.getenv("YOUTUBE_COOKIES", "")
    if cookies_env:
        with open(WORKING_COOKIES_PATH, "w", encoding="utf-8") as f:
            f.write(cookies_env)
        return WORKING_COOKIES_PATH
    
    return None

app.mount("/static", StaticFiles(directory="static"), name="static")

def cleanup_file(filepath: str):
    """Usuwa pobrany plik z dysku po wysłaniu go do użytkownika."""
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

    ydl_opts = {
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    # Podpięcie ciasteczek
    cookies_file = setup_cookies()
    if cookies_file:
        ydl_opts['cookiefile'] = cookies_file

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
        # POBIERANIE WIDEO: Pobiera gotowy, scalony plik (omija błąd braku formatu)
        ydl_opts.update({
            'format': 'best[ext=mp4]/bestvideo+bestaudio/best',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # Znajdź wygenerowany plik na podstawie unikalnego ID (zabezpieczenie na zmianę rozszerzenia przez ffmpeg)
        found_files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if unique_id in f]
        if found_files:
            filename = found_files[0]
        elif not os.path.exists(filename):
            raise HTTPException(status_code=500, detail="Plik nie został przetworzony poprawnie.")

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
