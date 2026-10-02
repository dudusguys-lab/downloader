import os
import shutil
import tempfile
from fastapi import FastAPI, HTTPException, Form, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="Media Downloader")

# Zezwolenie przeglądarce na połączenie
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Podpinamy folder ze stroną WWW
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

def kasuj_folder_tymczasowy(sciezka: str):
    """Usuwa pobrane pliki z serwera zaraz po tym, jak użytkownik je pobierze."""
    shutil.rmtree(sciezka, ignore_errors=True)

@app.post("/api/download")
async def pobierz_media(
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    format_type: str = Form(...)
):
    if not url.strip():
        raise HTTPException(status_code=400, detail="Wklej poprawny link!")

    # Tworzymy osobny, unikalny folder na to jedno pobranie
    temp_dir = tempfile.mkdtemp()
    szablon_pliku = os.path.join(temp_dir, "%(title)s.%(ext)s")

    # Ustawienia yt-dlp w zależności od wyboru MP3 lub MP4
    if format_type == "mp3":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': szablon_pliku,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'quiet': True,
        }
    elif format_type == "mp4":
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': szablon_pliku,
            'quiet': True,
        }
    else:
        raise HTTPException(status_code=400, detail="Zły format")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            sciezka_pliku = ydl.prepare_filename(info)

            if format_type == "mp3":
                sciezka_pliku = os.path.splitext(sciezka_pliku)[0] + ".mp3"

            if not os.path.exists(sciezka_pliku):
                raise HTTPException(status_code=500, detail="Błąd zapisu pliku.")

            # Zlecamy automatyczne usunięcie folderu po wysłaniu pliku
            background_tasks.add_task(kasuj_folder_tymczasowy, temp_dir)

            return FileResponse(
                path=sciezka_pliku,
                filename=os.path.basename(sciezka_pliku),
                media_type='application/octet-stream'
            )

    except Exception as e:
        kasuj_folder_tymczasowy(temp_dir)
        raise HTTPException(status_code=500, detail=f"Błąd: {str(e)}")