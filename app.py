import os
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
load_dotenv()
st.title("Interview Coach")
client = Groq(api_key=os.environ["GROQ_API_KEY"])
P = """You are a senior hiring manager who has interviewed hundreds of candidates for this kind of role. You are preparing your question list for a specific candidate.

Read the job description and write 6 questions you would genuinely ask.

What makes a good question here:
- It targets something SPECIFIC in this posting - a named tool, a stated responsibility, a described challenge. Not the general field.
- It cannot be answered with a rehearsed script. It should require the candidate to describe something they actually did.
- It reveals depth. A strong candidate and a weak one should give visibly different answers.

Avoid: 'tell me about yourself', 'what are your strengths', anything answerable without reading this posting, and anything a candidate could prepare from a generic list.

Write:
- 2 technical questions on skills named explicitly in the posting
- 2 behavioural questions tied to the responsibilities described
- 2 situational questions about problems someone in THIS role would actually hit

Format each as:
**N. [question]**
*What you are listening for: [one line on what separates a strong answer from a weak one]*

JOB DESCRIPTION:
"""
jd = st.text_area("Job description", height=250)
if st.button("Generate questions", type="primary"):
    r = client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "user", "content": P + jd}])
    st.markdown(r.choices[0].message.content)
