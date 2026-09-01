"""CJK Datasets and Frequency Lists for Production Stroke Pre-generation."""

from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

MAKEMEAHANZI_DICT_URL = "https://raw.githubusercontent.com/skishore/makemeahanzi/master/dictionary.txt"


def get_production_kanji_list(limit: int = 2500, cache_dir: Path | None = None) -> list[str]:
    """Return curated list of the top 2,500 Japanese Kanji (Joyo 2,136 + Jinmeiyo)."""
    seed_file = (cache_dir or Path("static/seed_data/strokes")) / "kanjivg_chars.json"
    if seed_file.exists():
        try:
            data = json.loads(seed_file.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 100:
                return data[:limit]
        except Exception:
            pass

    # Fallback default list
    raw_str = '一二三四五六七八九十百千万日月火水木金土天気雨上下左右中大小男女目耳手足口人名年円音学本力休見立出入休早夕花草竹林木森町村山川田校町石車犬白赤青空糸字文玉王正生引羽雲園遠何科夏家歌画会回海絵外角楽活岩顔汽記帰弓牛魚京強教近兄形計元言原戸古午前後光語公工広交光考行高合国黒今才細作算止市矢姉思紙寺自時室社弱首秋週春書少場色食心新親図数西声星晴切雪走多太体台地池知竹中昼長鳥朝直通弟冬刀当答同東頭道読南肉馬売買麦半番父風分聞米歩母方毎妹万明鳴毛門夜野友用曜来里理話悪安暗医委意育員院飲運泳駅央横屋温化界開階寒感漢館岸起期客究急級宮球去橋業曲局銀区苦具君係軽血決研県庫湖向幸港号根祭皿仕死使始指歯詩次事持式実写者主守取酒受州拾終習集住重宿所暑助昭消商章勝乗植申身神真深進世整昔全相送想息速族多他打対待代第題炭短談着注柱丁帳調追定庭笛鉄転都度投豆等動童農波配倍箱畑発反坂板皮碑秒平鼻氷服福物平並放法望牧末未味脈民無命油有遊予由優羊予洋旅両緑礼列路和愛案以衣位囲胃印英栄塩億加果貨課芽改械街各格完官管関観願希季紀喜旗器機議求泣救給挙漁共協鏡競極清訓軍郡径型景芸欠結建健験固功好候航康告差菜最材昨札刷殺察参散産残司史士氏試児治辞失借種周祝順初松笑唱焼照城縄職信臣成清静席積折節説浅戦選然争倉巣束側続卒孫帯隊達単置仲貯兆腸低底停的典伝徒努灯堂働特得毒熱念敗梅博白飯飛必票標不夫付府副粉兵別辺変便包法望牧末満未無約要養利陸良料量輪類令冷例歴連老労録圧移因永営衛易益液演応往桜可仮価河過快賀各確額刊歓幹慣眼基寄規技義逆久旧居許境均禁句群経件券険検限現減故個護効厚耕鉱構興講査再妻採際裁雑酸賛師士支志枝資飼示似識質舎謝授修述術準序招承証条状常情職織制勢性政製税責績接設舌絶専銭祖素総造増像臓蔵即俗測属率損退貸態団断築提程適敵統銅導徳独任燃能破判版犯比肥非費備評貧布婦武復複保墓報豊防貿易暴務迷綿脈盟模預余容乱略留領貸異遺域宇映延沿我灰拡閣革割株干巻看簡危機貴疑吸供胸郷勤筋系敬警劇激穴絹権憲後厳己呼誤后孝皇紅降骨困砂座蚕姿私至視詞誌磁射捨尺若樹宗就衆従縦縮熟純処署諸除将傷障城蒸針仁垂推寸誠聖誠宣専泉洗染善創奏層操窓装走退態大拓卓託達奪誕探暖段値忠庁頂潮賃痛展討党糖届難乳認納脳派拝背肺俳班晩否批秘腹奮並閉陛片補暮宝訪亡忘棒枚幕密訳優郵幼欲翌乱覧卵裏律臨朗論握扱依威為緯維偉壱逸芋姻隠韻疫栄謁越押奥宴憶臆獲嚇格岳顎掛冠勘寛歓勧患堪甘喚環艦鑑含頑企幾棋畿毀揮輝伎騎岐欺吸拒拠享凶恐峡脅郷響亨享拘郊控梗購巧綱貢豪克拷込鎖唆墾催彩採債載宰砕災裁采済細埼惨鍛柵伺賜雌旨肢脂遮爵酌釈寂寿需儒囚宗周執秀朱殊狩趣呪寿需宗舟秀秋酬獣狩銃潤循遵順准巡潤繕徐庶諸如叙宵匠昇肖訟粧召詳抄焦彰償硝礁賞症償錠醸譲拭触嘱侵審尋慎芯娠震浸振薪診陣尽迅甚陣澄須随睡髄粋枢推遂酔促即側速俗賊駄妥拓濁駄滞胎袋泰耐託濁択諾奪綻脱丹淡誕端弾壇治致遅畜窒蓄逐秩窒衷仲酎抽鋳駐眺兆超聴彫貼帳丁庁脹牒町潮懲挑頂沈爪吊釣呈廷逓艇堤程締泥摘適滴敵溺迭哲徹撤顛点添殿田電吐妬途渡堵斗透洞瞳胴匿得徳督読凸突届鈍曇軟難汝弐任認濡熱年粘納能膿把冴魁辻嶺岬咲渚雫葵蓮萌莉穂桜楓蘭遥翔颯湊悠陽琉蒼碧蓮樹拓瑠湊琉颯駿悠絃湊曖宛嵐畏椅萎茨嘘唄鬱疫詠悦謁怨宴淹旺臆怨佳架霞俄魁晦顎笠葛鎌鴨萱粥渇韓玩棺瓦毀机嗅泣鋸虚脇錦倶駒串窟卦慶憬桁隙桁鍵桁痕頃砦駒撒塞惨斬肢叱柴嫉奢遮邪蛇狩袖羞蹴醜儒汁呪殉憧宵鞘擾杖壌嬢嘱娠晨刃塵訊錐裾凄脆脊醒咳蹟拙膳狙遡揃遜汰唾苔叩濁誰綻蛋旦痴緻唾緻潰吊鶴挺梯低鄭溺洞妬謎鍋捺睨濡覗呑把這'
    seen = set()
    result = []
    for char in raw_str:
        if ord(char) > 0x2E80 and char not in seen:
            seen.add(char)
            result.append(char)
            if len(result) >= limit:
                break
    return result


def fetch_makemeahanzi_all_characters(cache_dir: Path | None = None) -> list[str]:
    """Fetch complete list of 9,500+ Chinese characters supported by MakeMeAHanzi."""
    cached_file = (cache_dir or Path("static/seed_data/strokes")) / "makemeahanzi_chars.json"
    if cached_file.exists():
        try:
            data = json.loads(cached_file.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 1000:
                return data
        except Exception as e:
            logger.warning("Could not read cached MakeMeAHanzi list: %s", e)

    chars: list[str] = []
    try:
        req = urllib.request.Request(MAKEMEAHANZI_DICT_URL, headers={"User-Agent": "Flama/1.0"})
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            for line in resp.read().decode("utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    ch = entry.get("character")
                    if ch and len(ch) == 1 and ch not in chars:
                        chars.append(ch)
                except Exception:
                    continue
    except Exception as e:
        logger.error("Failed to fetch MakeMeAHanzi dictionary online: %s", e)

    if chars:
        try:
            cached_file.parent.mkdir(parents=True, exist_ok=True)
            cached_file.write_text(json.dumps(chars, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    return chars


def get_production_hanzi_list(locale: str = "zh", limit: int = 9000, cache_dir: Path | None = None) -> list[str]:
    """Return curated list of Chinese Hanzi for production seeding.

    Uses locale-specific pre-split JSON files generated via OpenCC S↔T mapping:
      - zh_production_hanzi.json     → Simplified-only + shared characters
      - zh_hant_production_hanzi.json → Traditional-only + shared characters
    Falls back to starter lists when neither locale-specific nor MakeMeAHanzi data is available.
    """
    seed_root = cache_dir or Path("static/seed_data/strokes")
    norm_locale = str(locale or "zh").strip().lower()
    is_traditional = "hant" in norm_locale or "tw" in norm_locale or "hk" in norm_locale

    # 1. Try locale-specific pre-split file (preferred)
    locale_file = seed_root / ("zh_hant_production_hanzi.json" if is_traditional else "zh_production_hanzi.json")
    if locale_file.exists():
        try:
            data = json.loads(locale_file.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 100:
                return data[:limit]
        except Exception as e:
            logger.warning("Could not read locale-specific Hanzi list %s: %s", locale_file, e)

    # 2. Fallback: raw MakeMeAHanzi list (mixed S/T — legacy behavior)
    all_chars = fetch_makemeahanzi_all_characters(cache_dir=cache_dir)
    if all_chars:
        logger.warning(
            "Using unsplit MakeMeAHanzi list for locale '%s'. "
            "Run the generation script to create locale-specific files.",
            locale,
        )
        return all_chars[:limit]

    # 3. Last resort: hardcoded starter lists
    from app.services.strokes.dataset_builder import ZH_STARTER_HANZI, ZH_HANT_STARTER_HANZI
    if is_traditional:
        return ZH_HANT_STARTER_HANZI[:limit]
    return ZH_STARTER_HANZI[:limit]

