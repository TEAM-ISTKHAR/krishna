import os
import asyncio
import shutil
from config import autoclean

async def auto_clean(popped):
    try:
        rem = popped.get("file")
        if not rem:
            return
            
        if rem in autoclean:
            autoclean.remove(rem)
        
        count = autoclean.count(rem)
        if count == 0:
            if "vid_" not in rem and "live_" not in rem and "index_" not in rem:
                try:
                    if os.path.exists(rem):
                        os.remove(rem)
                except Exception:
                    pass
    except Exception:
        pass


async def periodic_cleaner():
    while True:
        # 10800 seconds = 3 hours
        await asyncio.sleep(10800) 
        
        directories_to_clean = ["downloads", "cache"] 

        for dir_path in directories_to_clean:
            if os.path.exists(dir_path):
                for filename in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception:
                        pass
