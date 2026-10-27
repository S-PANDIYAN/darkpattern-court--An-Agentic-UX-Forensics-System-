import time
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# List of URLs to scrape.
# Includes 5 example Indian platforms.
# Paste the remaining 145 URLs below.
TARGET_URLS = [
    # --- E-Commerce & Retail ---
    "https://www.amazon.in/",
    "https://www.flipkart.com/",
    "https://www.myntra.com/",
    "https://www.ajio.com/",
    "https://www.nykaa.com/",
    "https://www.tatacliq.com/",
    "https://www.meesho.com/",
    "https://www.snapdeal.com/",
    "https://www.reliancedigital.in/",
    "https://www.croma.com/",
    "https://www.vijaysales.com/",
    "https://www.jiomart.com/",
    "https://blinkit.com/",
    "https://www.zeptonow.com/",
    "https://www.bigbasket.com/",
    "https://www.lenskart.com/",
    "https://www.pepperfry.com/",
    "https://www.firstcry.com/",
    "https://www.shoppersstop.com/",
    "https://www.lifestylestores.com/",
    "https://www.maxfashion.in/",
    "https://www.westside.com/",
    "https://www.boat-lifestyle.com/",
    "https://www.gonoise.com/",
    "https://www.samsung.com/in/",
    "https://www.oneplus.in/",
    "https://www.mi.com/in/",
    "https://www.robocraze.com/",
    "https://www.thesouledstore.com/",
    "https://www.decathlon.in/",

    # --- Travel, Transport & Hospitality ---
    "https://www.makemytrip.com/",
    "https://www.goibibo.com/",
    "https://www.yatra.com/",
    "https://www.cleartrip.com/",
    "https://www.irctc.co.in/",
    "https://www.redbus.in/",
    "https://www.abhibus.com/",
    "https://www.ixigo.com/",
    "https://www.easemytrip.com/",
    "https://www.booking.com/",
    "https://www.agoda.com/",
    "https://www.oyorooms.com/",
    "https://www.fabhotels.com/",
    "https://www.treebo.com/",
    "https://www.goindigo.in/",
    "https://www.airindia.com/",
    "https://www.akasaair.com/",
    "https://www.spicejet.com/",
    "https://www.olacabs.com/",
    "https://www.uber.com/in/en/",
    "https://www.rapido.bike/",
    "https://www.blablacar.in/",
    "https://www.zoomcar.com/",
    "https://www.klook.com/en-IN/",
    "https://in.hotels.com/",

    # --- Food Delivery & Dining ---
    "https://www.zomato.com/",
    "https://www.swiggy.com/",
    "https://www.eatsure.com/",
    "https://dominos.co.in/",
    "https://www.pizzahut.co.in/",
    "https://online.kfc.co.in/",
    "https://mcdelivery.co.in/",
    "https://www.burgerking.in/",
    "https://www.faasos.com/",
    "https://www.behrouzbiryani.com/",
    "https://www.ovenstory.in/",
    "https://www.freshmenu.com/",
    "https://www.barbequenation.com/",
    "https://www.eazydiner.com/",
    "https://www.dineout.co.in/",
    "https://www.wendys.co.in/",
    "https://www.haldirams.com/",
    "https://www.bikanervala.com/",
    "https://www.chaayos.com/",
    "https://www.starbucks.in/",

    # --- Job Portals & EdTech ---
    "https://www.naukri.com/",
    "https://in.indeed.com/",
    "https://www.linkedin.com/",
    "https://www.shine.com/",
    "https://www.foundit.in/",
    "https://internshala.com/",
    "https://www.apna.co/",
    "https://www.glassdoor.co.in/",
    "https://unacademy.com/",
    "https://byjus.com/",
    "https://www.vedantu.com/",
    "https://www.simplilearn.com/",
    "https://www.upgrad.com/",
    "https://www.coursera.org/in",
    "https://www.udemy.com/",
    "https://www.scaler.com/",
    "https://www.pw.live/",
    "https://www.geeksforgeeks.org/",
    "https://www.freecodecamp.org/",
    "https://www.cuemath.com/",

    # --- Financial Services, Insurance & Crypto ---
    "https://paytm.com/",
    "https://www.phonepe.com/",
    "https://cred.club/",
    "https://www.policybazaar.com/",
    "https://www.bankbazaar.com/",
    "https://groww.in/",
    "https://zerodha.com/",
    "https://upstox.com/",
    "https://www.angelone.in/",
    "https://kuvera.in/",
    "https://www.etmoney.com/",
    "https://cleartax.in/",
    "https://www.hdfcbank.com/",
    "https://www.icicibank.com/",
    "https://sbi.co.in/",
    "https://www.axisbank.com/",
    "https://www.kotak.com/",
    "https://www.bajajfinserv.in/",
    "https://www.coinbase.com/",
    "https://coindcx.com/",

    # --- Entertainment, Ticketing & OTT ---
    "https://in.bookmyshow.com/",
    "https://insider.in/",
    "https://www.netflix.com/in/",
    "https://www.primevideo.com/",
    "https://www.hotstar.com/in/",
    "https://www.sonyliv.com/",
    "https://www.zee5.com/",
    "https://www.jiocinema.com/",
    "https://open.spotify.com/",
    "https://gaana.com/",
    "https://wynk.in/music",
    "https://www.pvrcinemas.com/",
    "https://www.inoxmovies.com/",
    "https://ticketnew.com/",
    "https://www.voot.com/",

    # --- Health, Real Estate & Services ---
    "https://www.practo.com/",
    "https://www.1mg.com/",
    "https://www.netmeds.com/",
    "https://www.apollopharmacy.in/",
    "https://pharmeasy.in/",
    "https://www.cult.fit/",
    "https://www.healthifyme.com/",
    "https://www.magicbricks.com/",
    "https://www.99acres.com/",
    "https://housing.com/",
    "https://www.nobroker.in/",
    "https://www.squareyards.com/",
    "https://www.shaadi.com/",
    "https://www.bharatmatrimony.com/",
    "https://www.jeevansathi.com/",
    "https://bumble.com/en-in/",
    "https://tinder.com/",
    "https://www.aisle.co/",
    "https://www.urbancompany.com/",
    "https://www.justdial.com/"
]

def main():
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Initialize webdriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    dataset_tasks = []
    
    try:
        for url in TARGET_URLS:
            print(f"Scraping {url}...")
            try:
                driver.get(url)
                # Allow React/Angular DOMs to fully render
                time.sleep(4)
                
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, "html.parser")
                
                # Completely extract() and destroy unwanted tags
                for tag in soup(["script", "style", "noscript", "meta", "header", "footer", "nav"]):
                    tag.extract()
                    
                # Extract text specifically from these tags
                target_tags = ['p', 'div', 'span', 'h1', 'h2', 'h3', 'a', 'button']
                
                seen_texts = set()
                
                for element in soup.find_all(target_tags):
                    text = element.get_text(strip=True)
                    # Filter: Only keep text chunks where 10 < len(text) < 400
                    if text and 10 < len(text) < 400:
                        # Deduplicate the extracted strings per website
                        if text not in seen_texts:
                            seen_texts.add(text)
                            dataset_tasks.append({
                                "data": {
                                    "text": text,
                                    "source_url": url
                                }
                            })
                            
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                continue
    finally:
        driver.quit()
        
    # Save the final output to dataset_tasks.json
    output_filename = "dataset_tasks.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(dataset_tasks, f, ensure_ascii=False, indent=4)
        
    print(f"Scraping complete. Saved {len(dataset_tasks)} chunks to {output_filename}.")

if __name__ == "__main__":
    main()
