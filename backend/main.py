import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def extract_meaningful_text(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return f"Failed to fetch {url}: {e}"

    soup = BeautifulSoup(response.text, 'html.parser')

    for tag in ['nav', 'footer', 'aside', 'script', 'style', 'form', 'iframe', 'noscript']:
        for element in soup.find_all(tag):
            element.decompose()

    content_divs = soup.find_all('div')
    largest_div = max(content_divs, key=lambda div: len(div.get_text(strip=True)), default=None)

    if not largest_div:
        return "Main content not found."

    raw_text = largest_div.get_text(separator=' ', strip=True)
    
    text = re.sub(r'\s+', ' ', raw_text)
    lines = text.split('. ')
    meaningful_lines = [line.strip() for line in lines if len(line.strip()) > 30]
    refined_text = '. '.join(meaningful_lines)
    
    return refined_text if refined_text else "Extracted text was too short or not meaningful."


def mail_gen(raw_text, name) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=OPENAI_API_KEY, temperature=0.9)
    
    prompt_template = PromptTemplate(
        input_variables=["raw_text","name"],
        template="""
            You are an AI email generator designed to craft professional and engaging business proposals. Based on the scraped website data provided, generate a customized email to the company outlining how our AI/ML solutions can enhance their business operations.
            Our company, Drema AI, specializes in revolutionizing businesses with tailored AI/ML solutions. We offer end-to-end custom AI/ML model development, advanced data analytics, seamless system integration, and post-deployment optimization. Our number +91 8104659927, +91 6205467465. Linkedin: https://www.linkedin.com/company/drema-ai/. email:- m@drema.in . My name is Mr.Purushottam Kumar (CEO, Drema AI).

            Name of the client: {name}
            Clint website: {raw_text}

            The email should:

            1. Address the recipient professionally.
            2. Mention specific details from their website that align with our services.
            3. Highlight how our AI/ML expertise can add value to their business.
            4. Offer a free consultation and an opportunity to discuss potential collaboration.
            5. Include our contact information.
            6. Do not leave anything empty in the mail.

            Maintain a friendly, persuasive, and professional tone.
            Ensure the email is concise, well-structured, and compelling.
        """
    )
    
    chain = prompt_template | llm
    mail_text = chain.invoke({"raw_text": raw_text, "name": name})
    return mail_text.content

def process_excel_to_csv(file_path, output_csv):
    links = pd.read_excel(file_path)
    
    data = []
    
    for index, row in links.iterrows():
        name = f"{row['First Name']} {row['Last Name']}"
        url = row['Website']
        email = row['Email']
        extracted_text = extract_meaningful_text(url)
        email_text = mail_gen(extracted_text, name)
        
        data.append({
            'Name': name,
            'Email': email,
            'URL': url,
            'Email_Text': email_text
        })
    
    df = pd.DataFrame(data)
    df.to_csv(output_csv, index=False)
    print(f"CSV file '{output_csv}' has been created successfully!")
    return data