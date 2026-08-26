from pathlib import Path
import httpx
from app.config import settings

async def convert_html_to_pdf(html_file_path: Path) -> bytes:
    """
    Envía un archivo HTML al servicio de Gotenberg para convertirlo a PDF.
    """
    url = f"{settings.GOTENBERG_URL}/forms/chromium/convert/html"
    
    async with httpx.AsyncClient() as client:
        with open(html_file_path, "rb") as f:
            files = {"files": (html_file_path.name, f, "text/html")}
            response = await client.post(url, files=files, timeout=30.0)
            
            if response.status_code != 200:
                raise RuntimeError(f"Gotenberg error {response.status_code}: {response.text}")
                
            return response.content
