# 📄 Document Diff Tool

A web-based tool for comparing PDF documents, detecting differences, and visualizing changes with highlighted outputs.

---

## 🚀 Overview

This project provides an end-to-end solution for document comparison:

1. Upload two PDF files
2. Extract text content
3. Detect differences (line & word level)
4. Generate highlighted images
5. Export change summaries as CSV
6. (Optional) Annotate differences using LLM

---

## 🖥 Demo Features

- 📂 Upload two PDF files
- 🔍 Detect inserted / deleted / modified text
- 🖼 Visualize differences with highlighted images
- 📊 Export results as CSV
- 🤖 Optional AI-based explanation (Ollama / Gemma)

---

## 🧱 Tech Stack

### Backend
- Python
- FastAPI
- PDF processing (custom pipeline)

### Frontend
- HTML / CSS / JavaScript (Vanilla)

### Other
- File handling & image rendering
- Optional LLM integration (Ollama)

---

## 📁 Project Structure
doc_diff_app/
├─ app/
│ ├─ main.py
│ ├─ routers/
│ └─ services/
├─ uploads/
├─ outputs/
├─ frontend/
│ ├─ index.html
│ ├─ script.js
│ └─ style.css
