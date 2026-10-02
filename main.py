import os
import uuid
import shutil
from fastapi import FastAPI, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import yt_dlp

app = FastAPI()

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

def cleanup_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Błąd usuwania pliku {filepath}: {e}")

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
        'quiet': False,
        'no_warnings': False,
    }

    # Pobieranie proxy ze zmiennej środowiskowej Rendera
    proxy_url = os.getenv("PROXY_URL")
    if proxy_url:
        ydl_opts['proxy'] = proxy_url

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
        ydl_opts.update({
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

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
