Regenerates ../Cahier_des_charges_Bestimetravel.docx

  python -m venv env
  env\Scripts\pip install python-docx matplotlib
  env\Scripts\python diagrams.py      (draws the two figures next to the scripts)
  env\Scripts\python build_cdc.py     (writes the .docx into ..\)
