# samples/ — realne klatki z kamer do dostrojenia detekcji

Tutaj wrzucaj zdjęcia ze swojego zestawu (3× kamera OV9732, lotki steel, tarcza
kremowo-czarna). Na tej podstawie dostroję kalibrację, progi różnicy tła,
wykrywanie końcówki grota i — jeśli trzeba — OCR pod czcionkę Twojej tarczy.

Po wrzuceniu napisz mi: **„są nowe próbki w samples/"**.

## Struktura

```
samples/
  calibration/          # PUSTA tarcza (bez lotek), po 1 zdjęciu z każdej kamery
    empty_cam0.png
    empty_cam1.png
    empty_cam2.png
  throws/               # rzuty: para before/after z każdej kamery
    throw01_cam0_before.png
    throw01_cam0_after.png
    throw01_cam1_before.png
    throw01_cam1_after.png
    throw01_cam2_before.png
    throw01_cam2_after.png
    throw02_cam0_before.png
    ...
  throws_ground_truth.csv   # co naprawdę rzuciłeś + co moduł pokazał
```

## Konwencja nazw (ważne — trzymaj się jej)

- Kamery: **`cam0`, `cam1`, `cam2`** (ta sama kamera zawsze pod tym samym numerem).
- Rzuty numerowane: **`throwNN`** (`throw01`, `throw02`, …).
- Fazy: **`before`** (tarcza tuż przed rzutem) i **`after`** (z wbitą lotką).
- Format: **PNG** (bezstratny, preferowany) lub JPEG. Bez zmiany rozdzielczości.

Jeśli nie masz „before" dla każdego rzutu — daj przynajmniej pustą tarczę
(`calibration/`); będzie użyta jako tło (gorzej działa przy kilku lotkach naraz).

## Co wypełnić w `throws_ground_truth.csv`

Dla każdego rzutu wpisz **co faktycznie rzuciłeś** oraz **co moduł wykrył/policzył**
(najcenniejsze są rozbieżności). Kolumny opisane w nagłówku pliku.

## Ile na start

- **1×** komplet kalibracyjny (pusta tarcza z 3 kamer).
- **~10–15 rzutów** rozłożonych po tarczy: kilka w single, po jednym w
  triple/double, **bull i 25**, oraz **kilka blisko granic** (styk sektorów,
  krawędź double) — to najlepiej pokazuje, gdzie dostroić progi.
- Opcjonalnie **1 surowa klatka na wprost** (do oceny dystorsji/ostrości OV9732).

## Uwagi sprzętowe (OV9732)

- Skadruj tak, by **cała tarcza + pierścień z cyframi** mieściły się w kadrze,
  tarcza możliwie **na środku** (moduły bywają szerokokątne → dystorsja na brzegach).
- **Równomierne oświetlenie** z przodu, bez odblasków na drutach i cieni grota.
- Odczyt po **znieruchomieniu lotki** (rolling shutter → unikamy rozmycia).

> Zdjęcia w tym folderze są śledzone przez git (`samples/**` jest wyłączone spod
> globalnego ignorowania obrazów, jeśli takie dodasz). Jeśli pliki są duże,
> możesz je też przesłać w czacie zamiast commitować.
