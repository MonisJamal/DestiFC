from renderz_api import search_fifarenderz
names = ["Mbappé", "Blanc", "Charlton", "Davies", "Gilberto Silva", "Shaqiri", "Nesta", "Diomandé", "Di Natale"]
for n in names:
    res = search_fifarenderz(n, size=5)
    print(f"{n}: {len(res)}")
