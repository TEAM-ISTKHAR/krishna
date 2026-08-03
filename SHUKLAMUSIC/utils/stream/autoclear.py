import os
import asyncio
import shutil
from config import autoclean

async def auto_clean(popped):
    """
    Ye function gaana play hone aur queue se hatne ke turant baad 
    local file ko server se delete kar dega.
    """
    try:
        rem = popped["file"]
        autoclean.remove(rem)
        count = autoclean.count(rem)
        if count == 0:
            # DHYAN DEIN: Yahan 'or' ki jagah 'and' lagana zaroori hai
            if "vid_" not in rem and "live_" not in rem and "index_" not in rem:
                try:
                    if os.path.exists(rem):
                        os.remove(rem)
                except:
                    pass
    except:
        pass


async def periodic_cleaner():
    """
    Ye ek background task hai jo har 24 ghante mein aapke 
    'downloads' folder ko poori tarah saaf (clear) kar dega.
    """
    while True:
        # 86400 seconds = 24 hours
        await asyncio.sleep(86400) 
        
        dir_path = "downloads" # Aapke bot ka download folder
        if os.path.exists(dir_path):
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                try:
                    # Agar file hai, toh usko delete karega
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.remove(file_path)
                    # Agar folder ke andar folder hai, toh use delete karega
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"File delete karne me error: {e}")
