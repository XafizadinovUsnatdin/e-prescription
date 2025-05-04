from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
from spellchecker import SpellChecker
from rapidfuzz import process
import pandas as pd

df = pd.read_csv(r"C:\Users\user\Downloads\dori_baza (1).csv")  # Fayl yo'lini to'g'ri kiritamiz
kasallik_bazasi = df.groupby("Kasallik nomi")["Tavsiya etilgan dorilar"].apply(list).to_dict()


model_name = "dbmdz/bert-large-cased-finetuned-conll03-english"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForTokenClassification.from_pretrained(model_name)
ner_pipeline = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")


spell = SpellChecker()
barcha_dorilar = df["Tavsiya etilgan dorilar"].unique()
spell.word_frequency.load_words([d.lower() for d in barcha_dorilar])

kasallik = "asthma"  # Masalan, foydalanuvchi kiritgan kasallik nomi
retsept = "The patient was prescribed Budeosonid."  # Foydalanuvchi kiritgan retsept


sozlar = retsept.split()
tuzatilgan_sozlar = [spell.correction(soz) if soz.isalpha() and soz.lower() not in barcha_dorilar and soz.isascii() else soz for soz in sozlar]
tuzatilgan_retsept = " ".join(tuzatilgan_sozlar)

print("🛠 Imlo tuzatilgan retsept:", tuzatilgan_retsept)


ner_natija = ner_pipeline(tuzatilgan_retsept)


dorilar_retseptda = []
for ent in ner_natija:
    word = ent["word"]
    if word.startswith("##"):
        dorilar_retseptda[-1] += word[2:]
    else:
        dorilar_retseptda.append(word)


dori_baza = kasallik_bazasi.get(kasallik.lower(), [])


to_gri = []
imlo_xato = []
notogri = []


for dori in dorilar_retseptda:
    if dori.lower() in [d.lower() for d in dori_baza]:
        to_gri.append(dori)
    else:
        result = process.extractOne(dori, dori_baza)
        if result:
            eng_yaqin, skor, _ = result
            if skor >= 80:
                imlo_xato.append((dori, eng_yaqin, skor))
            else:
                notogri.append(dori)
        else:
            notogri.append(dori)


print(f"📜 Retseptdagi dorilar: {dorilar_retseptda}")
print(f"✅ To‘g‘ri dorilar: {to_gri}")
print(f"✏️ Imlo xatolari: {imlo_xato}")
print(f"❌ Noto‘g‘ri dorilar: {notogri}")
