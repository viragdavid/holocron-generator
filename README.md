# Holocron Generator

The Holocron Generator is an automated content creation pipeline designed to generate unique Star Wars-themed short videos. It automates the process of scraping information from Wookieepedia, leveraging AI for narrative transformation and audio generation, creating dynamic video shorts with background footage and subtitles, and finally automating the upload process to YouTube.

This project showcases a comprehensive understanding of API integrations, automated workflows, multimedia processing, and data management.

👉 **Watch the generated videos here:** [Holocron Archives YouTube Channel](https://www.youtube.com/@HolocronArchives01)

## Project Overview

This project automates the end-to-end creation and publication of short-form video content based on Star Wars lore. It's a modular, multi-stage pipeline demonstrating full automation from data acquisition to public distribution.

## Automated Workflow

The entire process is orchestrated by a central `run-workflow.py` script, ensuring a seamless, automated pipeline from concept to completion. Each step runs sequentially, allowing for a structured and reliable content generation cycle.

## Key Components

The Holocron Generator is built upon five distinct, self-contained Python scripts, each responsible for a critical stage of the content pipeline:

1.  **Scraping (`scraper.py`)**:
    * **Functionality:** Gathers Star Wars article data from Wookieepedia, including text and image URLs. Incorporates robust logic for category filtering and preventing redundant processing.
    * **Technologies:** `requests`, `BeautifulSoup4` (bs4), `re`.

2.  **AI API Calls (`ai-api-calls.py`)**:
    * **Functionality:** Utilizes Google's generative AI (Gemini API) to rephrase and summarize scraped articles into concise video scripts. Generates high-quality voiceovers using Google Cloud Text-to-Speech (WaveNet).
    * **Technologies:** `google-generativeai`, `google-cloud-texttospeech`, `python-dotenv`.

3.  **Transcript Generation (`transcript-gen.py`)**:
    * **Functionality:** Creates precise SRT (SubRip Subtitle) files by performing force alignment of the generated audio with its corresponding text. This ensures accurate and readable subtitles for the videos.
    * **Technologies:** `forcealign`, `re`.

4.  **Video Generation (`video-gen.py`)**:
    * **Functionality:** Assembles the final video shorts. This involves compositing a chosen background video (e.g., Minecraft parkour footage) with AI-generated audio, overlaying relevant images from the article, and dynamically rendering subtitles.
    * **Technologies:** `moviepy`, `Pillow` (PIL), `numpy`, `requests`.

5.  **YouTube Upload (`youtube-upload.py`)**:
    * **Functionality:** Authenticates with the YouTube Data API and programmatically uploads the generated video shorts. Handles OAuth 2.0 flow, credential management, and setting video metadata (title, description, tags).
    * **Technologies:** `google-auth-oauthlib`, `google-api-python-client`, `python-dotenv`.

6.  **Main Script (`run-workflow.py`)**:
    * **Functionality:** Runs all the scripts above in after each other. When one scrit finishes it starts the next.
