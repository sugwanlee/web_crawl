import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--disable-infobars")
options.add_argument("--disable-extensions")
# options.add_argument("--start-maximized")
options.add_argument("--disable-gpu")
options.add_argument("--headless=new")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

#
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def get_info(url):
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    driver.get(url)
    try:

        more_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "ytd-text-inline-expander#description-inline-expander")))
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='count']/yt-formatted-string/span[2]")))
        more_button.click()
    except Exception as e:
        print(f"[더보기 클릭 생략] 에러: {e.__class__.__name__}")
        pass
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # 제목, 설명, 조회수, 업로드일, 제품 갯수, 제품 정보(이미지, 제품명, 구매링크, 가격)
    title = soup.find(attrs = {'id':'title'}).text.strip()
    description = soup.find(attrs = {'class':'style-scope ytd-text-inline-expander'}).text.strip()
    views_upload_date_product_count = soup.find(attrs = {'class':'style-scope ytd-watch-info-text'})
    spans = views_upload_date_product_count.find_all("span")
    views = spans[0].text.strip()
    upload_date = spans[2].text.strip()
    comment_count = soup.find('yt-formatted-string', class_='count-text style-scope ytd-comments-header-renderer').text
    if len(spans) > 4:
        product_count = spans[4].text.strip()
    else:
        product_count = ""
    if product_count:
        product_image = soup.find(attrs = {'class':'product-item-image style-scope ytd-merch-shelf-item-renderer no-transition'}).find(attrs = {'class':'style-scope yt-img-shadow'}).get("src")
        product_name = soup.find(attrs = {'class':'small-item-hide product-item-title style-scope ytd-merch-shelf-item-renderer'}).text.strip()
        product_link = soup.find(attrs = {'class':'product-item-description style-scope ytd-merch-shelf-item-renderer'}).text
        product_price = soup.find(attrs = {'class':'product-item-price style-scope ytd-merch-shelf-item-renderer'}).text.strip()
    else:
        product_image = ""
        product_name = ""
        product_link = ""
        product_price = ""

    driver.close()
    return title, description, views, upload_date, product_count, product_image, product_name, product_link, product_price, comment_count

urls = ["https://www.youtube.com/watch?v=Xchj7iJ-CUU", "https://www.youtube.com/watch?v=tF1Iok0Co94"]

data = []
for url in urls:
    title, description, views, upload_date, product_count, product_image, product_name, product_link, product_price, comment_count = get_info(url)

    data.append({
        "영상 제목": title,
        "영상 설명": description,
        "조회수": views,
        "업로드일": upload_date,
        "댓글 갯수": comment_count,
        "제품 갯수": product_count,
        "제품 이미지": product_image,
        "제품 이름": product_name,
        "제품 링크": product_link,
        "제품 가격": product_price,
    })

    df = pd.DataFrame(data)
    df.to_csv(f"long_crawler_{current_time}.csv", index=False)
print("✅ CSV 저장 완료")
