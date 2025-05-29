from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import urllib.parse
import requests
import pandas as pd
import warnings
import re
import os
import time, json, urllib
import io
from pydantic import BaseModel
from IPython.display import *

from google import genai
from google.genai import types
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from openai import OpenAI

# Global configuration for Gemini job evaluation
#GEMINI_API_KEY = ""
#RESUME_PATH = r'/Users/kathisnehith/Downloads/Ai_project_test/DataAnalyst_snehith_resume.pdf'
#MODEL_NAME = "gemini-2.0-flash-lite"
#JOB_TITLES = ['Data Analyst']
#LOCATIONS = ['Texas']
#SCROLL_LIMIT = 1

# Filters and thresholds for LinkedIn search
#EXPERIENCE_FILTER = '1,2'           # years-of-experience filter codes
#DATE_POSTED_FILTER = 'r48000'        # date-posted filter code
#MATCH_SCORE_THRESHOLD = 44          


class CandidateFit(BaseModel):
    score: int
    match_summary: str
    JD_exp: str
    candidate_exp: str
    strengths: list[str]
    drawbacks: list[str]
    priority_needs: list[str]
    domain: str
    sponsorship: str

# prompt for Gemini model

Model_instruction = """You are ResumeMatchAI — an ATS-compliant, recruiter-aware evaluator that analyzes how well a candidate's resume matches a job description. You do not write, rephrase, or improve content. Your only task is to compare and score match quality.

Your output must be deterministic, structured, and strictly based on visible resume content and job description criteria.

---
 Behavioral Rules and Logic:

1. **ATS + Recruiter Logic**
   - Simulate both Applicant Tracking System filters and real recruiter shortlisting behavior.
   - ATS = keyword/tool match; Recruiter = domain, outcomes, and seniority alignment.

2. **Scoring Criteria (0–100):**
   Evaluate the match based on these pillars:
   - **Essential Requirements:** Are non-negotiable needs met (e.g., years of experience, key tools like Salesforce, domain expertise like Telecom)?
   - **Demonstrated Capabilities:** Are skills shown through specific outcomes, tools, and metrics — not just mentioned?
   - **Transferable Experience:** If domain is different, are workflows, tools, or business impact highly relevant?
   - **Hiring Priorities:** Consider implicit expectations such as certifications, communication skills, Agile, or onsite readiness.

   Scoring Breakdown:
   - 0–19 →  Critical mismatch (missing multiple key requirements)
   - 20–39 →  Major mismatch (one or more essential elements missing)
   - 40–59 →  Partial relevance (transferable, but weak in direct alignment)
   - 60–79 →  Strong alignment (minor gaps only)
   - 80–100 →  Excellent match (ready-to-hire fit)

3. **No Over-Crediting**
   - Do not assume skills or experience.
   - Do not reward generic relevance unless mapped clearly to JD priorities.
   - Penalize if key qualifications are absent (even if related skills are present).

4. **No Verbose Text**
   - Output only structured, parseable JSON — handled by downstream `pydantic` models.
   - Keep all summaries tight, fact-based, and within token limits (e.g., match summary max 25 tokens).

---

Field Definitions (per CandidateFit)
	•	score (int): 0–100 per the established rubric.
	•	match_summary (str): One concise sentence (≤25 tokens) summarizing overall alignment.
	•	JD_exp (str): The job’s experience requirement (≤25 tokens), e.g. "8+ years in Salesforce BA (Service Cloud)".
	•	candidate_exp (str): What the resume actually shows (≤25 tokens), e.g. "2 years as Data Analyst".
	•	strengths (list[str]): 2–3 bullet points (≤75 tokens each) listing top relevant skills or outcomes.
	•	drawbacks (list[str]): 2–3 bullet points (≤75 tokens each) listing key missing requirements.
	•	priority_needs (list[str]): 2–3 items (≤75 tokens each) of recruiter’s highest concerns.
	•	domain (str): Single word or short phrase (≤10 tokens) describing industry (e.g., "Telecommunications").
	•	sponsorship (str): Either "Requires No Sponsorship" or "Sponsorship OK" based on JD language.

---

** strict things**
- Output only the structured JSON matching `CandidateFit`.
- Do not include any prose or explanation.
"""

User_prompt = "Evaluate the following resume(file attached) against the job description. Follow the system rules and return output only in the defined structured"


# --- Gemini Client/Job Search Functions ---
def init_gemini_client(API_KEY, model_name, system_prompt, resume, final_prompt):
    """
    Initializes the Gemini client, uploads the resume, and returns:
    - client: the Gemini client instance
    - uploaded_file: the uploaded resume file reference
    - config: the GenerateContentConfig for evaluation
    """
    client = genai.Client(api_key=API_KEY)
    uploaded_file = client.files.upload(file=resume)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        max_output_tokens=500,
        temperature=0.3,
        top_p=0.9,
        response_mime_type='application/json',
        response_schema=list[CandidateFit]
    )
    ai_response = client.models.generate_content(
                        model=model_name,
                        contents=[uploaded_file, final_prompt],
                        config=config
                    )
    return ai_response.text


def search_linkedin_jobs(
    job_titles,           # list of job titles (keywords)
    locations,            # list of locations
    experience_level,     # experience filter code (e.g., '1,2')
    time_posted,          # date posted filter code (e.g., 'r10800')
    Api_key,              # Gemini API key
    Model_name,           # Gemini model name
    Resume_doc,            # path to the resume file
    match_score_threshold  # minimum match score threshold
):
    """
    Searches LinkedIn for given job_titles and locations, evaluates each posting
    against the uploaded resume using Gemini, and returns a pandas DataFrame of results.
    """
    data = []
    total_jobs_extracted = 0
    final_col = [
        'Job_title', 'Job_location', 'Job_company', 'Post_date', 'Time_posted',
        'Post_link', 'Company_link', 'Job_description', 'Job_Level', 'Job_Type',
        'Application_Count', 'Salary', 'Hiring_Person', 'Hiring_Person_Link',
        'score', 'match_summary', 'JD_exp', 'candidate_exp', 'strengths',
        'drawbacks', 'priority_needs', 'domain', 'sponsorship'
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    
    for job_title in job_titles:
        for location in locations:
            getVars = {
                'keywords': job_title,
                'location': location,
                'sort': 'date',
                'start': '0',
                'f_E': experience_level,
                'f_TPR': time_posted
            }
            url = 'https://www.linkedin.com/jobs/search/?' + urllib.parse.urlencode(getVars)
            
            time.sleep(2)
            
            response = requests.get(url, headers=headers, verify=False)
            soup = BeautifulSoup(response.content, 'html.parser')
            postings = soup.find_all(
                'div',
                class_='base-card relative w-full hover:no-underline '
                      'focus:no-underline base-card--link '
                      'base-search-card base-search-card--link job-search-card'
            )

            for post in postings:
                total_jobs_extracted += 1
                # Extract fields...
                try:
                    title = post.find('h3', class_='base-search-card__title').text.strip()
                except:
                    title = "N/A"
                try:
                    loc = post.find('span', class_='job-search-card__location').text.strip()
                except:
                    loc = "N/A"
                try:
                    company = post.find('h4', class_="base-search-card__subtitle").text.strip()
                except:
                    company = "N/A"
                try:
                    date_posted = datetime.strptime(post.find('time')['datetime'], '%Y-%m-%d').date()
                except:
                    date_posted = "N/A"
                try:
                    link = post.find('a', class_='base-card__full-link')['href']
                except:
                    link = "N/A"
                try:
                    company_link = post.find('a', class_='hidden-nested-link')['href']
                except:
                    company_link = "N/A"

                # Fetch job page
                try:
                    resp = requests.get(link, headers=headers)
                    soup_job = BeautifulSoup(resp.content, 'html.parser')
                except:
                    continue

                # Extract additional details...
                try:
                    applicants = soup_job.find('figcaption', class_='num-applicants__caption')
                    app_count = re.search(r'\d+', applicants.text).group() if applicants else "N/A"
                except:
                    app_count = "N/A"
                try:
                    time_ago = soup_job.find('span', class_='posted-time-ago__text').text.strip()
                except:
                    time_ago = "N/A"
                try:
                    salary_block = soup_job.find('div', class_='compensation__salary-range')
                    salary = salary_block.text.strip() if salary_block else "N/A"
                except:
                    salary = "N/A"
                try:
                    hiring_section = soup_job.find('div', class_='base-main-card')
                    hiring_person = (
                        hiring_section.find('span', class_='sr-only').text.strip()
                        if hiring_section else "N/A"
                    )
                    hiring_link = (
                        hiring_section.find('a')['href']
                        if hiring_section else "N/A"
                    )
                except:
                    hiring_person = hiring_link = "N/A"
                try:
                    jd_block = soup_job.find('div', class_='show-more-less-html__markup')
                    description = jd_block.get_text(separator=" ", strip=True)
                except:
                    description = "N/A"

                job_level = job_type = "N/A"
                try:
                    criteria = soup_job.find_all('li', class_='description__job-criteria-item')
                    for item in criteria:
                        hdr = item.find('h3').text.strip()
                        val = item.find('span').text.strip()
                        if hdr == "Seniority level":
                            job_level = val
                        elif hdr == "Employment type":
                            job_type = val
                except:
                    pass

                # Evaluate with Gemini
                final_query = f"{User_prompt}\nJob Title: {title}\nCompany: {company}\nDescription: {description}"
                try:
                    output_text=init_gemini_client(Api_key, Model_name, Model_instruction, Resume_doc, final_query)
                    gem_data = json.loads(output_text)[0]
                except Exception as e:
                    print("????ERROR???? in GEmini response:", e)
                    continue

                if gem_data['score'] > match_score_threshold:
                    data.append([
                        title, loc, company, date_posted, time_ago,
                        link, company_link, description, job_level, job_type,
                        app_count, salary, hiring_person, hiring_link,
                        gem_data['score'], gem_data['match_summary'], gem_data['JD_exp'],
                        gem_data['candidate_exp'], gem_data['strengths'], gem_data['drawbacks'],
                        gem_data['priority_needs'], gem_data['domain'], gem_data['sponsorship']
                    ])
                    print(f"Added job: {title} -at {company} -with score {gem_data['score']} - {gem_data['match_summary']}")
    # Create DataFrame from collected data
    if data:
        df=pd.DataFrame(data, columns=final_col)
    else:
        df = pd.DataFrame(columns=final_col)
        print("No jobs found matching the criteria.")
    return df

#search_linkedin_jobs(JOB_TITLES, LOCATIONS, EXPERIENCE_FILTER, DATE_POSTED_FILTER,GEMINI_API_KEY, MODEL_NAME, RESUME_PATH)