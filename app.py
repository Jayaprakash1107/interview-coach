import os
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
load_dotenv()
st.title("Interview Coach")
client = Groq(api_key=os.environ["GROQ_API_KEY"])
P = "You are a hiring manager. Read this job description and write 6 interview questions you would actually ask: 2 technical, 2 behavioural, 2 situational. Be specific to this posting. Number them 1-6. JOB DESCRIPTION: "
jd = st.text_area("Job description", height=250)
if st.button("Generate questions", type="primary"):
    r = client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "user", "content": P + jd}])
    st.markdown(r.choices[0].message.content)
