# FormatLab Android — public APK build

Ez a repository kizárólag az **offline FormatLab Android v0.2.1** nyilvános, titok- és személyesadat-ellenőrzött forrásából készített teszt APK fordítására szolgál.

## Állapot

- A nyilvános GitHub Actions futtató elindul: [smoke run #39570881540](https://github.com/misssska/formatlab-android-public-build/actions/runs/39570881540) **PASS**.
- A `.github/workflows/build-public-android.yml` fordítási workflow telepítve.
- A forrás ZIP feltöltése **még hátravan**. **Nincs még lefordított APK.**
- A korábbi `misssska/formatlab-android-` repository privát marad.

## Androidos feltöltés Windows nélkül

1. A ChatGPT beszélgetésben töltsd le: **FormatLab-Android-public-v0.2.1-ellenorzott.zip**. Ne csomagold ki.
2. A GitHub webes felületén válaszd: [Upload files](https://github.com/misssska/formatlab-android-public-build/upload/main).
3. Töltsd fel pontosan erre a névre, a repository gyökerébe: `FormatLab-Android-public-v0.2.1-ellenorzott.zip`. A forrás nyilvánosan olvasható lesz.
4. **Commit changes** a `main` ágra. A build automatikusan indul: [GitHub Actions](https://github.com/misssska/formatlab-android-public-build/actions).
5. Sikeres futás után keresd az **Artifacts** szekcióban a `FormatLab-Android-v0.2.1-debug-APK` letöltést. Az APK-t az artifact ZIP kibontása után lehet telepíteni.

SHA-256 (kötelező):

```text
a1b72d9b8c8331e5c77c2b04330c77786596fd73c81064649b9b9c4d07e058ed
```

A workflow az archívum hashét és tartalmát ellenőrzi, majd futtatja a forrásbiztonsági és JavaScript-híd teszteket. Java 17 / Android SDK 35 / Gradle 8.10.2 környezetben debug APK-t próbál fordítani.

## Korlátok

- Az alkalmazás offline képfájl-, CSV/JSON-, ZIP- és megosztási funkciókra készült. PDF/Office, videó és részletes SVG csak külön szerverrel működne.
- Debug APK, nem Play Store-kiadás; valódi telefonos teszt még szükséges.
- Az ingyenes, nyilvános Actions futtatási idő rendelkezésre áll, de a fiók 0,5 GB-os Actions artifact-tárhelykerete betelt, ezért az APK artifact feltöltése külön blokkolódhat. A workflow egy napos megőrzést használ.
- Nem tehető ide hozzáférési kulcs, aláírókulcs, magánkonfiguráció vagy személyes adat.
