import os
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
load_dotenv()
st.title("Interview Coach")
client = Groq(api_key=os.environ["GROQ_API_KEY"])
P = open("prompt.txt", encoding="utf-8").read()
jd = st.text_area("Job description", height=250)
if st.button("Generate questions", type="primary"):
    r = client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "user", "content": P + jd}])
    st.markdown(r.choices[0].message.content)
