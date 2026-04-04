#!/bin/bash
cd "/Users/stevejobs/Desktop/Work Proj/Anima/program that checks trustpilot"
exec python3 -m streamlit run dashboard.py --server.port 8501 --server.headless true
