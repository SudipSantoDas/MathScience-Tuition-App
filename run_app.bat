@echo off
echo Starting MathScience Academy Platform...
pip install -r requirements.txt
python -m streamlit run app.py
pause