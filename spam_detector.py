import re
from dataclasses import dataclass, field

# Паттерны, характерные для спама. Дополняйте под свою аудиторию.
SPAM_KEYWORDS = [
    r"заработ[ао]к",
    r"крипт[ао]",
    r"казино",
    r"ставк[аи]",
    r"куплю",
    r"срочно",
    r"бесплатн[аяые]+",
    r"розыгрыш",
    r"выигр[аы]",
    r"инвестиц",
    r"пассивн[ый]+ доход",
    r"telegram\.me/joinchat",
    r"t\.me/\+",
    r"onlyfans",
    r"пиш[иы] в лс",
    r"пиш[иы] в личк",
    r"напиш[иы] мне",
    r"на\s+руки",
    r"подработк[аи]",
    r"свободн.*график",
    r"частичн.*занят",
    r"1-2\s*час",
    r"2-3\s*час",
    r"4\s*ooo|3\s*ooo|5\s*ooo",
    r"работа на дому",
    r"удал[её]нн[ая]+ работа",
    r"forex",
    r"бинарн[ые]+ опцион",
    # Криптовалюты — более широкие паттерны
    r"\bUSDT\b",
    r"\bUSDC\b",
    r"\bBTC\b",
    r"\bETH\b",
    r"\b(?:usdt?|usdc|btc|eth|ton|sol|doge|shib)\b",  # строчные варианты
    r"чек.*USDT?",
    r"получ.*USDT?",
    r"вывод.*USDT?",
    r"перевод.*USDT?",
    r"крипто.*чек",
    r"USDT?.*чек",
    r"\d+\s*USDT?\b",  # Сумма с валютой
]

SUSPICIOUS_URL_PATTERNS = [
    r"bit\.ly",
    r"tinyurl",
    r"goo\.gl",
    r"clck\.ru",
    r"cutt\.ly",
    r"rb\.gy",
    r"short\.link",
    # Крипто-связанные
    r"cryptobot",
    r"crypto.*bot",
    r"tonkeeper",
    r"pancake",
    r"uniswap",
    r"sushi\.com",
    r"1inch",
    r"dex\.\w+",
]

URL_RE = re.compile(r"https?://[^\s]+|t\.me/[^\s]+|@\w+", re.IGNORECASE)
CAPS_RE = re.compile(r"[A-ZА-ЯЁ]{5,}")
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)

# Диапазоны Unicode для разных алфавитов
CYRILLIC_RE = re.compile(r'[а-яё]', re.IGNORECASE)
LATIN_RE = re.compile(r'[a-z]', re.IGNORECASE)
GREEK_RE = re.compile(r'[\u0391-\u03C9]')  # Греческие буквы
SPECIAL_CHARS_RE = re.compile(r'[^\w\s@]')  # Спецсимволы (кроме @)
WORD_RE = re.compile(r'\b\w+\b')  # Для выделения слов


@dataclass
class SpamVerdict:
    is_spam: bool
    score: int
    reasons: list[str] = field(default_factory=list)


class SpamDetector:
    def __init__(self, threshold: int = 50) -> None:
        self.threshold = threshold
        self._keyword_res = [re.compile(p, re.IGNORECASE) for p in SPAM_KEYWORDS]
        self._url_res = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_URL_PATTERNS]

    def _check_mixed_alphabets(self, text: str) -> tuple[int, list[str]]:
        """Проверка на смешение алфавитов и подозрительные символы в словах."""
        score = 0
        reasons = []
        
        # Проверка наличия разных алфавитов во всем тексте
        has_cyrillic = bool(CYRILLIC_RE.search(text))
        has_latin = bool(LATIN_RE.search(text))
        has_greek = bool(GREEK_RE.search(text))
        
        alphabet_count = sum([has_cyrillic, has_latin, has_greek])
        
        if alphabet_count >= 2:
            # Проверяем каждое слово отдельно
            words = WORD_RE.findall(text)
            mixed_words = 0
            greek_words = 0
            
            for word in words:
                word_has_cyrillic = bool(CYRILLIC_RE.search(word))
                word_has_latin = bool(LATIN_RE.search(word))
                word_has_greek = bool(GREEK_RE.search(word))
                
                # Слово содержит буквы из разных алфавитов
                word_alphabets = sum([word_has_cyrillic, word_has_latin, word_has_greek])
                
                # Проверка на греческие буквы в слове (маскировка)
                if word_has_greek and not word_has_latin and not word_has_cyrillic:
                    greek_words += 1
                elif word_alphabets >= 2:
                    mixed_words += 1
                    
                    # Проверка на замену букв похожими символами из другого алфавита
                    # Например: "а" (рус) vs "a" (лат), "е" (рус) vs "e" (лат)
                    lookalike_pairs = [
                        ('а', 'a'), ('е', 'e'), ('о', 'o'), ('р', 'p'),
                        ('с', 'c'), ('у', 'y'), ('х', 'x'), ('к', 'k'),
                        ('м', 'm'), ('н', 'h'), ('т', 't'), ('в', 'b')
                    ]
                    
                    for cyr, lat in lookalike_pairs:
                        if (cyr in word.lower() and lat in word.lower()) or \
                           (any(c in word for c in 'АаВвЕеНнОоРрСсТтУуХх') and
                            any(c in word for c in 'ABCcEeHhKkMmOoPpTtXxYy')):
                            score += 10
                            reasons.append(f"подмена букв в слове: {word[:20]}")
                            break
            
            if mixed_words > 0:
                score += 20 * mixed_words
                reasons.append(f"смешанные алфавиты в {mixed_words} словах")
            
            if greek_words > 0:
                score += 20 * greek_words
                reasons.append(f"греческие буквы в {greek_words} словах")
        
        # Проверка на избыток спецсимволов в словах
        words = WORD_RE.findall(text)
        special_in_words = 0
        for word in words:
            if len(word) > 3:  # Игнорируем короткие слова
                special_chars = SPECIAL_CHARS_RE.findall(word)
                if len(special_chars) > 0:
                    special_ratio = len(special_chars) / len(word)
                    if special_ratio > 0.3:  # Более 30% спецсимволов
                        special_in_words += 1
        
        if special_in_words > 0:
            score += 10 * special_in_words
            reasons.append(f"спецсимволы в {special_in_words} словах")
        
        return score, reasons

    def analyze(
        self,
        text: str | None,
        *,
        has_forward: bool = False,
        is_new_member: bool = False,
        username: str | None = None,
    ) -> SpamVerdict:
        score = 0
        reasons: list[str] = []
        content = (text or "").strip()
        combined = content
        if username:
            combined = f"{username} {content}"

        for pattern in self._keyword_res:
            if pattern.search(combined):
                score += 35
                reasons.append(f"ключевое слово: {pattern.pattern}")
                break

        urls = URL_RE.findall(content)
        if urls:
            score += 20
            reasons.append(f"ссылки ({len(urls)})")

            for url in urls:
                for pattern in self._url_res:
                    if pattern.search(url):
                        score += 35
                        reasons.append("сокращённая/подозрительная ссылка")
                        break

        if len(content) > 0:
            caps = CAPS_RE.findall(content)
            caps_ratio = sum(len(c) for c in caps) / len(content)
            if caps_ratio > 0.5 and len(content) > 20:
                score += 15
                reasons.append("избыток CAPS")

            emojis = EMOJI_RE.findall(content)
            emoji_count = sum(len(e) for e in emojis)
            if emoji_count >= 5:
                score += 10
                reasons.append(f"много emoji ({emoji_count})")

        if has_forward:
            score += 15
            reasons.append("пересланное сообщение")

        if is_new_member and urls:
            score += 20
            reasons.append("новый участник + ссылка")

        # Проверка на смешанные алфавиты и подозрительные символы
        alphabet_score, alphabet_reasons = self._check_mixed_alphabets(combined)
        score += alphabet_score
        reasons.extend(alphabet_reasons)

        # Повторяющиеся символы: "!!!!!", "?????"
        if re.search(r"(.)\1{4,}", content):
            score += 10
            reasons.append("повторяющиеся символы")

        # Много упоминаний @user
        mentions = re.findall(r"@\w+", content)
        if len(mentions) >= 3:
            score += 20
            reasons.append(f"массовые упоминания ({len(mentions)})")

        score = min(score, 100)
        return SpamVerdict(is_spam=score >= self.threshold, score=score, reasons=reasons)