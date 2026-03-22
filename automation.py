import os
import asyncio
import pandas as pd
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# --- [설정] 관리 대상 호텔 리스트 ---
WATCHLIST = [
    "Four Seasons Hotel Seoul", "Lotte Hotel Seoul", "LOTTE CITY HOTEL MYEONGDONG",
    "ENA Suite Hotel Namdaemun", "HOTEL THE BOTANIK SEWOON MYEONGDONG", "Grand Hyatt Seoul",
    "The Westin Josun Seoul", "Royal Hotel Seoul", "Novotel Ambassador Seoul Dongdaemun",
    "L7 MYEONGDONG", "voco Seoul Myeongdong", "Courtyard by Marriott Seoul Myeongdong",
    "Conrad Seoul", "Le Méridien Seoul Myeongdong", "NINE TREE BY PARNAS MYEONGDONG 2",
    "Crown Park Hotel", "Four Points by Sheraton Myeongdong", "Four Points by Sheraton Seoul Station",
    "Solaria Nishitetsu Hotel Seoul Myeongdong", "Fairfield by Marriott Seoul", 
    "L'Escape Hotel", "Aloft Seoul Myeongdong", "NINE TREE BY PARNAS INSADONG",
    "THE PLAZA Seoul", "Sejong Hotel", "Koreana Hotel", "Moxy Seoul Myeongdong",
    "ibis Styles Ambassador Myeongdong", "NINE TREE BY PARNAS MYEONGDONG 1",
    "Hotel Skypark Kingstown Dongdaemun", "Banyan Tree Club & Spa Seoul",
    "Skypark Central Seoul Pangyo", "NINE TREE BY PARNAS DONGDAEMUN",
    "ibis Ambassador Seoul Myeongdong", "Hotel Skypark Central Myeongdong", "Sono Calm Goyang"
]

def run_scraping():
    results = []
    with sync_playwright() as p:
        iphone = p.devices['iPhone 13']
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(**iphone)
        page = context.new_page()

        for hotel in WATCHLIST:
            try:
                print(f"🔍 Analyzing: {hotel}")
                page.goto(f"https://www.google.com/search?q={hotel.replace(' ', '+')}+prices", timeout=60000)
                page.wait_for_timeout(5000)

                ota_data = {}
                # 더 넓은 범위의 선택자로 변경 (구글의 변화에 대비)
                content = page.content()
                
                # 정규표현식으로 가격과 OTA 이름을 직접 매칭하는 방식 (더 강력함)
                for ota in ["Expedia", "Hotels.com", "Booking.com", "Agoda"]:
                    pattern = rf"{ota}.*?₩\s?([\d,]+)"
                    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                    if match:
                        ota_data[ota] = int(match.group(1).replace(',', ''))

                exp_price = ota_data.get("Expedia") or ota_data.get("Hotels.com")
                comp_price = min(filter(None, [ota_data.get("Booking.com"), ota_data.get("Agoda")]), default=None)

                if exp_price and comp_price:
                    diff_pct = round(((exp_price - comp_price) / comp_price) * 100, 1)
                    results.append({
                        "Hotel": hotel, "Expedia": exp_price, "Competitor": comp_price, 
                        "Diff_%": diff_pct, "Status": "🔴 Lose" if diff_pct > 0 else "🟢 Beat"
                    })
            except Exception as e:
                print(f"Error at {hotel}: {e}")
        
        browser.close()
    return pd.DataFrame(results)

def send_email(df):
    if df.empty: return
    
    sender = "bignail.choi@gmail.com"
    # GitHub Secrets에서 비밀번호를 가져오도록 설정
    password = os.environ.get("GMAIL_PASSWORD") 
    
    msg = MIMEMultipart()
    msg['Subject'] = f"🚨 [BML Report] {len(df[df['Diff_%'] >= 10])}개 호텔 긴급 점검 필요"
    msg['From'] = sender
    msg['To'] = sender

    # HTML 리포트 생성
    urgent = df[df['Diff_%'] >= 10]
    html = f"""
    <h3>📊 Expedia BML Daily Report</h3>
    <h4 style='color:red;'>⚠️ 긴급 (Gap > 10%): {len(urgent)}건</h4>
    {urgent.to_html(index=False)}
    <br>
    <h4>📍 전체 현황</h4>
    {df.to_html(index=False)}
    """
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)

if __name__ == "__main__":
    data = run_scraping()
    send_email(data)