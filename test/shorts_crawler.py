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
# 크롬 옵션 설정
options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--disable-infobars")
options.add_argument("--disable-extensions")
options.add_argument("--start-maximized")
options.add_argument("--disable-gpu")
options.add_argument("--headless=new")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")


def get_views_and_upload_date(url):
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    driver.get(url)
    
    search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "yt-shorts-video-title-view-model.ytShortsVideoTitleViewModelHostClickable")))
    search_box.click()
    
    # 페이지가 로드될 때까지 잠시 대기
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#title yt-formatted-string")))
    
    # BS4로 렌더링된 HTML 파싱
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # 1) 제목 추출
    # div#title 안의 yt-formatted-string 전체 텍스트
    title_elem = soup.select_one("div#title yt-formatted-string")
    title = title_elem.get_text(strip=True)

    # 2) 조회수 추출 (aria-label에 '조회수' 포함)
    views_elem = soup.find(lambda tag: tag.has_attr("aria-label") and "조회수" in tag["aria-label"])
    views = views_elem["aria-label"].replace("조회수 ", "").replace("회", "").strip()

    # 3) 업로드 날짜 추출 (aria-label에 마침표 두 번 이상)
    date_elem = soup.find(
        lambda tag: tag.has_attr("aria-label") and tag["aria-label"].count(".") >= 2
    )
    try:
        raw = date_elem["aria-label"]
        # "2025. 5. 2." -> ["2025", "5", "2"]
        parts = [p.strip() for p in raw.replace(".", "").split()]
        year, month, day = parts

        # 두 자리 포맷 적용
        month = month.zfill(2)
        day   = day.zfill(2)

        upload_date = f"{year}-{month}-{day}"  # -> "2025-05-02"
    except TypeError as e:
        print(f"[에러] {url} 처리 중 날짜 문제 발생: {e}")
        upload_date = datetime.now().strftime("%Y-%m-%d")
        print("오늘 날짜로 처리")
    driver.close()
    return title, views, upload_date


def get_channel_info(url):
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    driver.get(url)

    channel_name = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='page-header']/yt-page-header-renderer/yt-page-header-view-model/div/div[1]/div/yt-dynamic-text-view-model/h1/span"))).text
    subscribers = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='page-header']/yt-page-header-renderer/yt-page-header-view-model/div/div[1]/div/yt-content-metadata-view-model/div[2]/span[1]"))).text
    subscribers = subscribers.replace("구독자 ", "").replace("명", "")

    if '만' in subscribers:
        num = float(subscribers.replace('만', ''))
        subscribers = int(num * 10_000)
    
    # '천' 단위
    elif '천' in subscribers:
        num = float(subscribers.replace('천', ''))
        subscribers = int(num * 1_000)
    
    # 그 외: 이미 정수 문자열
    else:
        subscribers = int(subscribers)
    
    driver.close()
    return channel_name, subscribers


def get_shorts_urls(url):
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(url)
        
        SCROLL_PAUSE_TIME = 2
        shorts_urls = set()

        last_height = driver.execute_script("return document.documentElement.scrollHeight")

        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            WebDriverWait(driver, SCROLL_PAUSE_TIME).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            elements = driver.find_elements(By.XPATH, "//*[@id='content']/ytm-shorts-lockup-view-model-v2/ytm-shorts-lockup-view-model/a")
            for element in elements:
                shorts_urls.add(element.get_attribute("href"))

            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            print(f"현재 수집된 Shorts 개수: {len(shorts_urls)}")

            if new_height == last_height:
                WebDriverWait(driver, SCROLL_PAUSE_TIME).until(
                    lambda d: d.execute_script("return document.documentElement.scrollHeight") == new_height
                )
                break
            last_height = new_height

        return list(shorts_urls)
    finally:
        driver.close()


this_time = datetime.now().strftime("%Y-%m-%d")
stack_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def get_info(urls):
    data = []

    for url in urls:
        channel_name, subscribers = get_channel_info(url)
        shorts_urls = get_shorts_urls(url)

        for shorts_url in shorts_urls:
            try:
                title, views, upload_date = get_views_and_upload_date(shorts_url)
                data.append({
                    "누적집계일" : stack_time,
                    "추출일": this_time,
                    "채널명": channel_name,
                    "영상 제목": title,
                    "영상 링크": shorts_url,
                    "업로드일": upload_date,
                    "조회수": views,
                    "구독자 수": subscribers
                })
                print(f'{title} 완료')
            except Exception :
                print(f"[에러] {shorts_url} 처리 중 크롤링 문제 발생")
                for i in range(3):
                    try:
                        title, views, upload_date = get_views_and_upload_date(shorts_url)
                        data.append({
                            "누적집계일" : stack_time,
                            "추출일": this_time,
                            "채널명": channel_name,
                            "영상 제목": title,
                            "영상 링크": shorts_url,
                            "업로드일": upload_date,
                            "조회수": views,
                            "구독자 수": subscribers
                        })
                        print(f'{title} 재시도 성공')
                        break
                    except Exception as e:
                        print(f"[에러] {shorts_url} 재시도 중 문제 발생")

    df = pd.DataFrame(data)
    count = 0
    file_name = f"shorts_info_{count}.csv"
    while os.path.exists(file_name):
        count += 1
        file_name = f"shorts_info_{count}.csv"
    df.to_csv(f"data/{file_name}", index=False, encoding="utf-8-sig")
    print(f"✅ CSV 저장 완료: {file_name}")



# urls = ["http://www.youtube.com/channel/UC8nUDc4Fc4VvZkRP1oePY-w",]
urls = ["https://www.youtube.com/@%EC%9C%A0%ED%8A%9C%EB%B8%8C%EC%88%98%EC%9D%B5%ED%99%94%EB%B8%8C%EB%9E%9C%EB%94%A9/shorts",]
# "http://www.youtube.com/channel/UCp8p0NTwUjxU5G3ZqEn2FQg",
# "http://www.youtube.com/channel/UCkavWA4JMTdOKfLr1Qilx8g"]

start_time = time.time()
get_info(urls)
end_time = time.time()
print(f"총 실행 시간: {end_time - start_time:.2f}초")
