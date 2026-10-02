import os
import uuid
import shutil
import requests
from fastapi import FastAPI, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import yt_dlp

app = FastAPI()

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

def get_free_proxy():
    """Pobiera świeże darmowe proxy w locie, żeby omijać bana IP na Renderze."""
    try:
        response = requests.get(
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=yes",
            timeout=5
        )
        proxies = [p.strip() for p in response.text.splitlines() if p.strip()]
        if proxies:
            return f"http://{proxies[0]}"
    except Exception as e:
        print(f"Nie udało się pobrać proxy: {e}")
    return None

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

    # Automatyczne podstawienie darmowego proxy
    proxy = get_free_proxy()
    if proxy:
        print(f"Używam proxy: {proxy}")
        ydl_opts['proxy'] = proxy
    else:
        print("Brak proxy, próba bezpośredniego połączenia...")

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
