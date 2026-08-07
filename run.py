"""
SPC Tool Web - Statistical Process Control Tool (Web Version)
Entry point for Dash application.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
