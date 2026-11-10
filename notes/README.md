<!-- Purpose: explain where a fresh checkout gets its PDF source material. -->
<!-- Work: document filenames and indexing while keeping course PDFs out of Git. -->

# Add your PDF notes here

Place numerical analysis PDFs directly in this folder. Original course PDFs are kept locally and excluded from Git; cloning this repository does not download the notes.

For automatic week filters, use filenames such as:

```text
Week_1_Numerical_Analysis.pdf
Week_9_Numerical_Analysis.pdf
Week_16_Numerical_Analysis.pdf
```

Other `.pdf` filenames are also included under **All notes**. Use unique names so existing files are not overwritten.

From the project root, after dependency and model setup:

```powershell
.\venv\Scripts\python.exe ingest.py
```

Stop the API before indexing to free model memory. After a successful build, restart the API and click **Refresh library** in the frontend. Existing unchanged page OCR is reused; new/changed PDFs need processing, and the vector index is rebuilt.
