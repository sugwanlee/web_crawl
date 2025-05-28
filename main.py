import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime, timedelta
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
import time
# 크롬 옵션 설정
options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--disable-infobars")
options.add_argument("--disable-extensions")
options.add_argument("--start-maximized")
options.add_argument("--disable-gpu")
options.add_argument("--headless=new")
options.add_argument("--log-level=3")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")


def get_views_and_upload_date(url):
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(url)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "ytd-structured-description-content-renderer")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        root = soup.find("ytd-structured-description-content-renderer")

        if not root:
            raise Exception("루트 태그를 찾을 수 없습니다.")

        # 1️⃣ 제목 + 해시태그 (공백 유지)
        title_elem = root.select_one("#title yt-formatted-string")
        title = title_elem.get_text(separator=" ", strip=True) if title_elem else "[제목 없음]"

        # 2️⃣ 조회수
        views_elem = root.find(lambda tag: tag.name == "div" and tag.has_attr("aria-label") and "조회수" in tag["aria-label"])
        views = views_elem["aria-label"].replace("조회수 ", "").replace("회", "").strip() if views_elem else "0"

        # 3️⃣ 업로드 날짜
        date_elem = root.find(lambda tag: tag.name == "div" and tag.has_attr("aria-label") and "." in tag["aria-label"])
        if date_elem:
            raw = date_elem["aria-label"]
            parts = [p.strip() for p in raw.replace(".", "").split()]
            year, month, day = parts
            month = month.zfill(2)
            day = day.zfill(2)
            upload_date = f"{year}-{month}-{day}"
        else:
            upload_date = ""

        return title, views, upload_date

    except Exception as e:
        print(f"[에러] {url} 처리 중 문제 발생: {e}")
        return "", "0", ""

    finally:
        driver.quit()



def get_channel_info(url):
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    driver.get(url)

    channel_name = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='page-header']/yt-page-header-renderer/yt-page-header-view-model/div/div[1]/div/yt-dynamic-text-view-model/h1/span"))).text
    try:
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
        
    except TimeoutException:
        subscribers = "정보없음"
    
    driver.quit()
    return channel_name, subscribers


def get_shorts_urls(url):
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(url)
        shorts_urls = set()
        last_urls_count = 0
        retry_count = 0
        max_retries = 2
        max_scroll_retries = 3

        while retry_count < max_retries:
            scroll_retries = 0

            while scroll_retries < max_scroll_retries:
                try:
                    # 요소 재조회
                    elements = driver.find_elements(By.XPATH, "//*[@id='content']/ytm-shorts-lockup-view-model-v2/ytm-shorts-lockup-view-model/a")
                    current_urls = set()

                    for elem in elements:
                        try:
                            href = elem.get_attribute("href")
                            if href and "shorts" in href:
                                current_urls.add(href)
                        except StaleElementReferenceException:
                            continue  # 무시하고 다음 요소로

                    shorts_urls.update(current_urls)

                    # 새로 추가된 URL이 없으면 retry 증가
                    if len(shorts_urls) == last_urls_count:
                        retry_count += 1
                    else:
                        retry_count = 0
                        last_urls_count = len(shorts_urls)
                        print(f"현재 수집된 Shorts 개수: {len(shorts_urls)}")

                    # 스크롤 전 높이 저장
                    last_height = driver.execute_script("return document.documentElement.scrollHeight")

                    # 스크롤 실행
                    driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
                    time.sleep(1)  # DOM 안정화 대기

                    # 스크롤 완료 여부 확인
                    def is_scroll_complete(driver):
                        current_height = driver.execute_script("return document.documentElement.scrollHeight")
                        scroll_position = driver.execute_script("return window.pageYOffset + window.innerHeight")
                        return current_height > last_height or scroll_position >= current_height

                    try:
                        WebDriverWait(driver, 2).until(is_scroll_complete)
                        break  # 스크롤 완료, 내부 재시도 루프 탈출
                    except TimeoutException:
                        print("스크롤이 완료되지 않아 재시도합니다...")
                        scroll_retries += 1

                except Exception as e:
                    print(f"알 수 없는 에러 발생: {e}")
                    scroll_retries += 1

        return list(shorts_urls)

    finally:
        driver.quit()

stack_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
current_time = datetime.now().strftime("%y%m%d-%H%M")
crawl_time = datetime.now().strftime("%Y-%m-%d")
file_name = f"shorts_info_{current_time}.csv"

def get_info(urls):
    for url in urls:
        url = f'{url}/shorts'
        data = []
        channel_name, subscribers = get_channel_info(url)
        shorts_urls = get_shorts_urls(url)

        for shorts_url in shorts_urls:
            try:
                title, views, upload_date = get_views_and_upload_date(shorts_url)
                data.append({
                    "누적집계일": stack_time,
                    "추출일": crawl_time,
                    "채널명": channel_name,
                    "영상 제목": title,
                    "영상 링크": shorts_url,
                    "업로드일": upload_date,
                    "조회수": views,
                    "구독자 수": subscribers
                })
                print(f'{title} 완료')
            except Exception:
                print(f"[에러] {shorts_url} 처리 중 크롤링 문제 발생")
                for i in range(3):
                    try:
                        title, views, upload_date = get_views_and_upload_date(shorts_url)
                        data.append({
                            "누적집계일": stack_time,
                            "추출일": crawl_time,
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

        # 데이터 저장 (누적 저장 방식)
        if data:
            df = pd.DataFrame(data)
            file_path = f"data/{file_name}"

            # 파일 존재 여부 체크
            file_exists = os.path.isfile(file_path)
            df.to_csv(
                file_path,
                mode='a',                # append mode
                header=not file_exists,  # 처음 저장이면 header 추가
                index=False,
                encoding="utf-8-sig"
            )
            print(f"✅ CSV 저장 완료: {file_name}")




# urls = ['http://www.youtube.com/channel/UCuO9qb9PdlO_WFWd_wrTBkg', 'http://www.youtube.com/channel/UC1lhiz5lHfCw2rLZWqwhxnw', 'http://www.youtube.com/channel/UCgeTWh3tYz3LwkhCzbUsVzQ', 'http://www.youtube.com/channel/UC4LrX_37ZWrNcMS2NtXgKrA', 'http://www.youtube.com/channel/UCO8gltLqmlaN3a6M9i55OLA', 'http://www.youtube.com/channel/UCrRSAxplRF1_3MjoMC9_W9Q', 'http://www.youtube.com/channel/UCjHC_N682cOiH3GZ4AjeCDQ', 'http://www.youtube.com/channel/UCvBvw9pYAP5tB2quJ-BiF_A', 'http://www.youtube.com/channel/UC31ZzQkagJzsSHg2a0MXLeA', 'http://www.youtube.com/channel/UCi1Z70ZED1eCl8dJB9E4JTw', 'http://www.youtube.com/channel/UClL7bo4m9EmOGgSyn2oGfvA', 'http://www.youtube.com/channel/UC2_aGeWBT47euc6w5MCF2lw', 'http://www.youtube.com/channel/UCYwLHEPzSNs8v1Ko4hJonAg', 'http://www.youtube.com/channel/UCeUlwIfwei6U3VnTsUxNC9w', 'http://www.youtube.com/channel/UC8nUDc4Fc4VvZkRP1oePY-w', 'http://www.youtube.com/channel/UCKIBIgAKYheiaaC7hVHJzrQ', 'http://www.youtube.com/channel/UCp8p0NTwUjxU5G3ZqEn2FQg', 'http://www.youtube.com/channel/UCkavWA4JMTdOKfLr1Qilx8g', 'http://www.youtube.com/channel/UC2hfZKwDwWmhuqJbjKEh3aQ', 'http://www.youtube.com/channel/UCcN0eBs98KRjSoqBaPLq1jw', 'http://www.youtube.com/channel/UCFS3tu-34eounHIcU9Hu_xg', 'http://www.youtube.com/channel/UCYbqe2OyzTyPn8-vtUCJM6Q', 'http://www.youtube.com/channel/UC4Lv-mrKtNwv1YNZUpw1ftw', 'http://www.youtube.com/channel/UCfnmh_tZqEA095970xoPhUQ', 'http://www.youtube.com/channel/UCpyYMUbVskUHlOrPrGfT4Rw', 'http://www.youtube.com/channel/UC1TQrg-nROTEyRFewdoORyQ', 'http://www.youtube.com/channel/UC_hbyIBAKfTNXbQU8p5YHzg', 'http://www.youtube.com/channel/UCZ5e3Gd0BTbOLIfTWlcbReA', 'http://www.youtube.com/channel/UCAA_OMo9r0b-iUs3VrPuwPw', 'http://www.youtube.com/channel/UCHisNUl3gc00Ywy-o0ttypw', 'http://www.youtube.com/channel/UCbnz_dXMThEAaq5lz6q6IGA', 'http://www.youtube.com/channel/UCijXlGG2r5Onjo4NnB29zbw','http://www.youtube.com/channel/UCCi4CqLzemXkZ-6fQC3A3ag']
urls = ['https://www.youtube.com/@%EC%87%BC%EC%B8%A0%EB%AA%85%EC%9E%91-q9z']
start_time = time.time()
get_info(urls)
end_time = time.time()
print(f"총 실행 시간: {end_time - start_time:.2f}초")
