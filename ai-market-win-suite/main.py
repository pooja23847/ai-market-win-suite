"""
AI Market-Win Suite — Entry Point
Run this file to launch the Streamlit app:
    python main.py
Or run directly:
    streamlit run app.py
"""
import subprocess
import sys
import os

if __name__ == "__main__":
    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    print("⚡ Starting AI Market-Win Suite...")
    print("   Open your browser at: http://localhost:8501")
    print("   Demo login: demo@marketwin.ai / demo123")
    print("   Press Ctrl+C to stop.\n")
    subprocess.run([sys.executable, "-m", "streamlit", "run", app_path], check=True)
