import gradio as gr
import nest_asyncio, asyncio, os, aiohttp, aiofiles, glob, shutil
from playwright.async_api import async_playwright
from PIL import Image
from datetime import datetime

# Patch event loop for Gradio
nest_asyncio.apply()

# ---------- CONFIG ----------
USERNAME = "punkesari123@sjgoel.33mail.com"
PASSWORD = "iD54^2I#L$"
LOGIN_URL = "https://epaper.punjabkesari.in/login"
# ----------------------------

async def fetch_pages(page, url, edition_name):
    """Navigate, zoom, and fetch xl.png image URLs for a given edition"""
    await page.goto(url)
    await page.wait_for_timeout(3000)

    # Zoom twice
    for _ in range(2):
        await page.click("button.zoomPlus")
        await page.wait_for_timeout(1000)

    # Collect images
    await page.wait_for_selector("img.custImg")
    img_links = []
    for img in await page.query_selector_all("img.custImg"):
        src = await img.get_attribute("src")
        if src and src.endswith("xl.png"):
            img_links.append(src)

    img_links = list(dict.fromkeys(img_links))  # dedupe
    print(f"✅ {edition_name}: Found {len(img_links)} pages")
    return img_links


async def run(date_str):
    final_pdf = f"Ludhiana_Bathinda_{date_str}.pdf"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()

        # 1. Login
        await page.goto(LOGIN_URL)
        await page.fill("#txtemail", USERNAME)
        await page.fill("#txtpwd", PASSWORD)
        await page.click("button.logg")
        await page.wait_for_timeout(5000)

        # 2. Ludhiana edition
        LUDHIANA_URL = f"https://epaper.punjabkesari.in/punjab/{date_str}/main-ludhiana"
        ludhiana_links = await fetch_pages(page, LUDHIANA_URL, "Main Ludhiana")

        # 3. Bathinda edition
        BATHINDA_URL = f"https://epaper.punjabkesari.in/punjab/{date_str}/bathinda-kesari"
        bathinda_links = await fetch_pages(page, BATHINDA_URL, "Bathinda Kesari")

        await browser.close()

        # Merge order: Ludhiana first, Bathinda second
        all_links = ludhiana_links + bathinda_links

        # 4. Download images
        os.makedirs("pages", exist_ok=True)
        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(all_links, start=1):
                async with session.get(url) as resp:
                    if resp.status == 200:
                        fname = f"pages/page_{i:02d}.png"
                        async with aiofiles.open(fname, mode="wb") as f:
                            await f.write(await resp.read())

        # 5. Merge into single PDF
        png_files = sorted(glob.glob("pages/page_*.png"))
        images = [Image.open(f).convert("RGB") for f in png_files]
        images[0].save(final_pdf, save_all=True, append_images=images[1:])

    return final_pdf


def fetch_newspaper(date_str):
    """Wrapper for Gradio: takes text, enforces YYYY-MM-DD format, returns PDF"""
    try:
        # Validate format
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        clean_date = dt.strftime("%Y-%m-%d")
    except Exception as e:
        return None, f"❌ Invalid date. Please use YYYY-MM-DD. Error: {e}"

    # Run the async downloader
    pdf_file = asyncio.run(run(clean_date))

    return pdf_file, f"✅ Newspaper ready for {clean_date}"


# ---------- GRADIO UI ----------
with gr.Blocks() as demo:
    gr.Markdown("# 📰 Punjab Kesari E-Paper Downloader")

    date_input = gr.Textbox(
        label="Enter date (YYYY-MM-DD)",
        placeholder="e.g. 2025-08-30"
    )

    output_file = gr.File(label="Download Newspaper PDF")
    status = gr.Textbox(label="Status", interactive=False)

    fetch_btn = gr.Button("Fetch Newspaper")
    fetch_btn.click(
        fn=fetch_newspaper,
        inputs=date_input,
        outputs=[output_file, status]
    )

demo.launch(server_port=7860, server_name="0.0.0.0")
