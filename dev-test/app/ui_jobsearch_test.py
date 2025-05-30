import streamlit as st
import time
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.linkedinsearch import search_linkedin_jobs
import pandas as pd

GEMINI_MODEL = "gemini-2.0-flash-lite"

st.set_page_config(page_title="GetHire - Job Search Assistant", layout="wide", initial_sidebar_state="auto")
st.title("GetHire - Job Search Assistant")
st.subheader("Job Search Feature")


with st.sidebar:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    st.markdown("[Get an Gemini API key](https://aistudio.google.com/)", help="Using the link-Navigate over Get API Key, to create a new API key.")
    st.markdown("[Sample DE_Resume(Download)](https://drive.google.com/file/d/1lXAjCY4JrlrwdW1xrTAPBaCSj78fD1bk/view)", help="Download a sample resume to test the job search feature.")


uploaded_resume_file = st.file_uploader(
    "Drag and drop file here",
    type=["pdf"],
    help="Limit 32MB per file. TXT, DOCX, PDF",
    key="resume_uploader"
)
if uploaded_resume_file is not None:
    st.write(f"Uploaded: {uploaded_resume_file.name} ({uploaded_resume_file.size / 1024 / 1024:.2f} MB)")

# Remove st.form and move all widgets outside

st.markdown("---") 
# Create two rows of columns
col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

# First row inputs
with col1:
    job_titles = st.text_input(
        "Enter job titles separated by commas",
        placeholder="e.g., Data Engineer, \"ML Engineer\"....",
        help="Use quotes for precise job titles scrape",
        key="jobtitle_input",
    )
with col2:
    locations = st.text_input(
        "Enter locations separated by commas",
        placeholder="e.g., New York, Texas, California, USA",
        help="use locations of states or countries",
        key="location_input",
    )

# Second row inputs
with col3:
    experience_level = st.multiselect(
        "Experience level",
        ["Internship","Entry Level", "Mid Level", "Senior Level"],
        help="Select one or more experience levels",
        key="experience_select"
    )
with col4:
    date_posted = st.selectbox(
        "Date Posted",
        ["1hr", "2hr", "3hr", "6hr", "Last 24hr","Past Week", "Last 30 days"],
        help="Select the time frame-focused for todau's job postings",
        index=None,
        key="date_posted_select"
    )

# Toggle options (outside form)
easy_apply = st.toggle("Easy Apply", value=False, key="easy_apply_form_toggle")
under_10_applicants = st.toggle("Under 10 Applicants", value=False, key="under_10_form_toggle")
match_score_threshold = st.slider("Minimum Match Score", min_value=0, max_value=100, value=44)

if job_titles:
    jobtitles_list = [item.strip() for item in job_titles.split(',') if item.strip()]
    #print("location-Output list:", jobtitles_list)

if locations:
    location_list = [item.strip() for item in locations.split(',') if item.strip()]
    #print("location-Output list:", location_list)

if experience_level:
    experience_code_map = {
    "Internship": "1",
    "Entry Level": "2",
    "Mid Level": "3",
    "Senior Level": "4"
    }
    # Map selected experience levels to codes
    codes_experience_level = ",".join([experience_code_map[exp] for exp in experience_level])
    #print("Experience codes:", codes_experience_level)
    #st.write("Selected experience codes:", codes_experience_level)

if date_posted:
    date_posted_map = {
"1hr": "r3600",
"2hr": "r7200",
"3hr": "r10800",
"6hr": "r21600",
"Last 24hr": "r86400",
"Past Week": "r604800",
"Last 30 days": "r2592000"
    }
    code_time_posting = date_posted_map[date_posted]
    #print("Time posting code for URL:", code_time_posting)
    st.write("selected Time posting code: ", code_time_posting)

st.markdown("---") 
print("UI Form Inputs:------------------")
print("job titles: ",job_titles)
print("Locations: ", locations)
print("Experience Level: ", experience_level)
print("Date Posted: ", date_posted)
print("Under 10 Applicants: ", under_10_applicants)
print("Easy Apply: ", easy_apply)
print("---------------------------")
# Replace st.form_submit_button with a regular button
submitted = st.button(" Search Jobs", icon="🔍", use_container_width=True, key="search_jobs_button")

# Handle button click
if submitted:
    with st.spinner("Searching..."):
        time.sleep(2)
        st.write(f"Job Titles: {job_titles}")
        time.sleep(1)
        st.write(f"Locations: {locations}")
        time.sleep(1)
        st.write(f"Experience: {experience_level}, Posted: {date_posted}")
        st.write(f"Easy Apply: {easy_apply}, Under 10 Applicants: {under_10_applicants}")
        if uploaded_resume_file:
            st.success(f"Using resume: {uploaded_resume_file.name}")

        # --- Call LinkedIn job search and display results ---
        # Only proceed if all required fields are present
        if job_titles and locations and experience_level and date_posted and uploaded_resume_file and GEMINI_API_KEY:
            # Save uploaded resume to a temp file for passing to search_linkedin_jobs
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_resume:
                tmp_resume.write(uploaded_resume_file.read())
                resume_path = tmp_resume.name

            # Call the search function
            df= search_linkedin_jobs(
                jobtitles_list,
                location_list,
                codes_experience_level,
                code_time_posting,
                GEMINI_API_KEY,
                GEMINI_MODEL,
                resume_path,
                match_score_threshold
            )
            st.info("Hang on!! Job search extraction, filtering, and analysis in progress...")
            st.warning("This may take 1-2 minutes depending on level of elements selected")
            if isinstance(df, pd.DataFrame) and not df.empty:
                st.success(f" Found {len(df)} jobs matching your criteria.")
                for idx, row in df.iterrows():
                    with st.container(border=True):
                        col1_job, col2_job = st.columns([3, 1])
                        with col1_job:
                            st.subheader(f"{row['Job_title']}")
                            st.write(f"🏢 {row['Job_company']} | 📍 {row['Job_location']}")
                            st.write(f"**Type:** {row['Job_Type']} | **Posted:** {row['Post_date']}")
                            if row['Post_link'] and row['Post_link'] != "N/A":
                                st.link_button("Apply Now 🔗", row['Post_link'], type="secondary")
                            st.markdown(f"**Description:** {row['Job_description'][:300]}{'...' if len(row['Job_description']) > 300 else ''}")
                        with col2_job:
                            st.metric("Resume Match", f"{row['score']}%")
                            st.caption(f"Match Summary: {row['match_summary']}")
                        with st.expander("🔍 Show Gemini AI Analysis", expanded=False):
                            st.markdown(f"**JD Experience:** {row['JD_exp']}")
                            st.markdown(f"**Candidate Experience:** {row['candidate_exp']}")
                            st.markdown("**Strengths:**")
                            for s in row['strengths']:
                                st.write(f"- {s}")
                            st.markdown("**Drawbacks:**")
                            for d in row['drawbacks']:
                                st.write(f"- {d}")
                            st.markdown("**Priority Needs:**")
                            for p in row['priority_needs']:
                                st.write(f"- {p}")
                            st.markdown(f"**Domain:** {row['domain']}")
                            st.markdown(f"**Sponsorship:** {row['sponsorship']}")
            else:
                st.warning(f" No jobs!! found matching the criteria.")
        else:
            st.warning("Please fill all required fields and upload your resume.")
