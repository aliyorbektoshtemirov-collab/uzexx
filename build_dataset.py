"""CSV -> siqilgan SQLite (dasturchi uchun). Ishlatish: python build_dataset.py <uzex_spot_data papkasi>"""
import sys, os, market_data as md
src = sys.argv[1]; out = os.path.join("data", md.DB_NAME)
md.build_db(src, out); md.pack_db(out, os.path.join("data", md.GZ_NAME)); os.remove(out); md.split_gz(os.path.join("data", md.GZ_NAME))
