# Steam Achievement Inspector (SAI)

A desktop tool to analyze Steam achievements and highlight **suspicious unlocks**, typically produced by tools like [**Steam Achievement Manager (SAM)**](https://github.com/gibbed/SteamAchievementManager).  
It fetches a profile’s games and achievements, sorts them by time, and lets you filter anomalies.

> This project is not affiliated with Valve/Steam. For research/moderation use.

## How to use

- Enter **Steam profile URL** (`profiles/<steamid64>`, `id/<vanity>`, or raw steamid64).
- Enter your **Steam Web API Key** ([how to get it](#how-to-get-a-steam-web-api-key)).
- Click **Load**. If nothing appears or only partial data loads, see [Why it might show nothing](#why-it-might-show-nothing).

Then sort by time, filter identical timestamps or short time gaps, tune the **suspicious** threshold (Δt, minutes), and export to CSV with metadata.

### How to get a Steam Web API Key

1. Sign in to Steam.
2. Go to <https://steamcommunity.com/dev/apikey>
3. Fill in any domain (e.g., `localhost`), approve via Mobile Authenticator, obtain the key. **Do not share** your key; if leaked, revoke and create a new one.
4. Copy the **32-char hex** key and paste it into the app.

### Why do I need to get some code for this?

To fetch any user data, we need to query Valve’s databases. That’s exactly what the API is for. It gives us access to a user’s **public** data so we can process it in different ways. There’s nothing prohibited about this — everything goes through Steam’s official website.


---

## What counts as “suspicious”

- **Identical timestamps** → multiple achievements unlocked in the same second.
- **Δt ≤ N minutes** → unusually short time between unlocks.

## Why this is not proof of cheating

- **Identical timestamps** can happen due to save-file restores, achievements added later by devs, meta-achievements (“get all achievements”), offline play syncing later, or some types of bug in the game.
- **Short gaps** may happen with related/progressive achievements or lucky streaks.  
  Focus on *hard* achievements across *different* games appearing in a short window.


---

## Why it might show nothing

- The profile is **fully private**.
- A **specific game** is hidden — you won’t get data for it, only for visible ones.


---

## Install & run

1. Open repository **[Releases](../../releases)**.
2. Download `SteamAchievementInspector-<version>-win-x64.zip`.
3. Unzip and run `SteamAchievementInspector.exe`.


---

## Author

Steam: [SqwireX](https://steamcommunity.com/id/sqwirex/)  

If this tool helped, great! You can also audit your own profile — and if you ever used [SAM](https://github.com/gibbed/SteamAchievementManager), consider revoking “unearned” achievements and re-earning them properly.


---

---

# Steam Achievement Inspector (SAI) - Russian

Инструмент для быстрого анализа достижений Steam и поиска **подозрительных разблокировок**, характерных для выдачи через [**Steam Achievement Manager (SAM)**](https://github.com/gibbed/SteamAchievementManager).  
Приложение подтягивает список игр профиля, все полученные достижения, сортирует по времени и позволяет отфильтровать «аномалии».

> Проект не связан с Valve/Steam и предназначен для исследовательских и модерационных задач.

---

## Как использовать и что нужно

- Введите **URL профиля Steam** (поддерживаются `profiles/<steamid64>`, `id/<vanity>` и чистый steamid64).
- Введите **Steam Web API Key** ([как получить](#как-получить-steam-web-api-key)).
- Нажмите **Загрузить** и ожидайте подгрузки всех игр и достижений (если не грузит или грузит частично — см. раздел [почему может ничего не показывать](#почему-может-ничего-не-показывать)).

Далее вы можете сортировать достижения по времени получения, фильтровать по достижениям с одинаковым таймстампом или с маленькой разницей во времени, ставить собственные **подозрения** по времени между достижениями (Δt), меняя значение N, а также экспортировать полученные данные в CSV со всеми метаданными.

### Как получить Steam Web API Key

1. Войдите в Steam.
2. Перейдите на: <https://steamcommunity.com/dev/apikey>
3. Заполните домен (можно любой, например `localhost`), подтвердите выдачу ключа через мобильное приложение и получите ключ. **Никому не показывайте** свой API-ключ; если утёк — деактивируйте по той же ссылке и создайте новый.
4. Скопируйте **32-символьный** ключ (hex) и вставьте в приложение.

### Зачем мне получать какой-то код ради этого

Для того чтобы получить какие-либо данные о пользователе, нужно обратиться к базе данных Valve. Именно для этого и нужен API. С помощью него мы получаем доступ к **открытым** данным о пользователе и делаем с ними различные махинации. Ничего запрещенного в этом нет, все делается через официальный сайт стима.

---

## Как это определяет «подозрительные»

- **Одинаковый таймстамп** → несколько достижений получены в одну и ту же секунду.
- **Δt ≤ N минут** (и > 0 сек) → время между достижениями слишком маленькое.

## Почему это НЕ доказательство накрутки, а лишь сигнал к проверке

- **Одинаковый таймстамп**: перенос старых сейвов, добавление достижений пост-фактум разработчиком, связанные достижения (например «получи все достижения»), оффлайн-игра с последующей синхронизацией, различные баги в игре.
- **Малый интервал**: связанные/накопительные достижения, удачные стрики в одной сессии.  
  Смотрите прежде всего на *сложные* достижения из разных игр, появившиеся в узком интервале.

---

## Почему может ничего не показывать

- Профиль пользователя **полностью скрыт** — в таком случае вы не увидите ничего.
- Скрыта **конкретная игра** — по ней данные не загрузятся, будут только по открытым играм.

---

## Установка и запуск

1. Откройте вкладку **[Releases](../../releases)** этого репозитория.
2. Скачайте архив `SteamAchievementInspector-<версия>-win-x64.zip`.
3. Распакуйте и запустите `SteamAchievementInspector.exe`.

---

## Автор

Steam: [SqwireX](https://steamcommunity.com/id/sqwirex/)  

Рад, если эта простая тулза вам помогла. Её можно использовать не только для «расследований», но и чтобы проверить собственный профиль. Если когда-то баловались с [SAM](https://github.com/gibbed/SteamAchievementManager) — через него же можно отобрать у себя «нечестные» ачивки и закрыть их честно.
