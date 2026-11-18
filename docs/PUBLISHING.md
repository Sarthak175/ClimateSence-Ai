# Making the notebook and the website publicly accessible

## Colab notebook
1. Push the repo to **public GitHub**. Anyone can open the notebook with one link:
   `https://colab.research.google.com/github/<your-user>/climatesense-ai/blob/main/notebooks/ClimateSense_AI_ML_Training.ipynb`
   (add this as an "Open in Colab" badge in the README).
2. Or share a copy from Drive: upload to Colab → **Share** (top right) → *General access → Anyone with the link → Viewer* (use *Commenter/Editor* only if you want edits).
3. A public Colab link shows the notebook **with saved outputs**. Run all cells once, then **File → Save** (keep outputs) before sharing so faculty can read the real results without re-running. Clear secrets: there are none in this notebook.

## Website
* Frontend URL from Vercel (`https://<project>.vercel.app`) is public by default. Disable *Vercel Authentication / Deployment Protection* for preview deployments if you share them.
* Backend URL from Render is public; `/docs` provides the interactive API reference.
* Share both links plus the GitHub link in the report. Optional: add a custom domain in the Vercel project settings.

## Repository checklist (public)
- [ ] `README.md` with live links and screenshots
- [ ] `.env` is **not** committed (only `.env.example`)
- [ ] `backend/models/` committed (trained artifacts) and `data/raw/dataset_metadata.json`
- [ ] Licence note: weather data © Open-Meteo.com (CC BY 4.0, non-commercial free tier); NOAA GML & NASA GISS data are public - cite them.
- [ ] Notebook outputs saved
