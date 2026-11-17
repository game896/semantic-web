# Dnevnik

- Upoznao sam se sa tim šta je CRIS: sistem za evidenciju naučnog rada u kome su veze (ko je napisao koji rad, u kom je časopisu, koga citira) tačno zapisane u bazi.
- Napravio sam mali CRIS za istu oblast: iz OpenAlex-a sam učitao radove osam seed autora u SQLite bazu sa tabelama za radove, autore, časopise, ključne reči i citate.
- Dodao sam jednostavan web interfejs sa gotovim pitanjima (koautori, najveći časopisi, najcitiraniji radovi) i stranicama za autore, radove i časopise.
- Uporedio sam dva pristupa: CRIS tačno odgovara na pitanja poput "ko su koautori", ali pretraga nalazi samo doslovne reči; embedding pronalazi radove slične po značenju, ali ne zna sigurno ko je šta napisao.
- Istražio sam kako embedding može da predstavi radove, autore, pojmove i časopise u jednom prostoru, gde se povezanost računa kao sličnost.
