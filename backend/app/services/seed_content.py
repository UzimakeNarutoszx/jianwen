from sqlalchemy.orm import Session

from sqlalchemy import text as sql_text

from app.models.content import (
    AiAnswerRule,
    AiPrompt,
    ClassicBook,
    ClassicBookChapter,
    ContentArticle,
    ContentCategory,
    ContentFeature,
    ContentPage,
    DailyQuote,
)
from app.services.classic_fulltext import has_complete_qstheory_full_text, import_classic_full_texts


CATEGORIES = [
    ("党和国家", "/static/images/党和国家.png", True),
    ("共产党", "/static/images/共产党.png", True),
    ("时政大事", "/static/images/政策解读.png", True),
    ("就业", "/static/images/就业.png", False),
    ("住房", "/static/images/住房.png", False),
    ("科技", "/static/images/科技产业.png", False),
    ("医保", "/static/images/医保社保.png", False),
    ("消费", "/static/images/消费补贴.png", False),
    ("城市生活", "/static/images/社会民生.png", False),
]


ARTICLES = [
    {
        "article_id": "party-state",
        "category": "党和国家",
        "topic": "党和国家",
        "title": "党和国家机构怎样协同推进一项政策？",
        "desc": "把会议部署、部门分工、地方落实和公开信息放在一条线中看。",
        "sources": "中国政府网 / 新华网",
        "read_time": "5分钟",
        "image": "/static/images/党和国家.png",
        "relation": "普通公民 / 办事群众 / 政策关注者",
        "summary": ["会议部署", "部门分工", "地方落实"],
        "sections": [
            {"heading": "先区分方向和执行", "body": "很多政策先有总体部署，再由相关国家机关和部门制定细则。"},
            {"heading": "部门分工决定入口", "body": "同一项政策可能涉及多个部门，查询和申请入口通常落在具体主管部门或地方平台。"},
            {"heading": "地方细则决定体感", "body": "普通人真正感受到的政策，往往来自本地细则和办事流程。"},
        ],
        "references": [
            {"title": "国务院部门政策文件与公开信息", "org": "中国政府网", "date": "公开发布", "url": "https://www.gov.cn/"},
            {"title": "党和国家重要会议与政策报道", "org": "新华网", "date": "公开发布", "url": "https://www.news.cn/"},
        ],
        "is_today": True,
        "is_latest": True,
        "today_order": 1,
        "sort_order": 1,
    },
    {
        "article_id": "party",
        "category": "共产党",
        "topic": "共产党",
        "title": "理解中国共产党，先看哪几个基础问题？",
        "desc": "从组织体系、会议文件和基层治理三个入口建立基本框架。",
        "sources": "共产党员网 / 人民网",
        "read_time": "5分钟",
        "image": "/static/images/共产党.png",
        "relation": "基层党员 / 社区居民 / 公共事务关注者",
        "summary": ["组织体系", "会议文件", "基层治理"],
        "sections": [
            {"heading": "先看组织怎样运转", "body": "更实际的入口是组织体系：中央、地方、基层组织分别承担什么功能。"},
            {"heading": "文件是理解政策的线索", "body": "读这类内容时，重点看关键词、任务分工和后续配套政策。"},
            {"heading": "基层治理离生活最近", "body": "社区服务、志愿服务、基层协商和网格治理，是普通人更容易接触到的部分。"},
        ],
        "references": [
            {"title": "党的建设与党员教育相关公开信息", "org": "共产党员网", "date": "公开发布", "url": "https://www.12371.cn/"},
            {"title": "中国共产党相关公开报道与资料", "org": "人民网", "date": "公开发布", "url": "https://www.people.com.cn/"},
        ],
        "is_today": True,
        "is_latest": True,
        "today_order": 2,
        "sort_order": 2,
    },
    {
        "article_id": "current-affairs",
        "category": "时政大事",
        "topic": "时政大事",
        "title": "看一条时政新闻，先抓哪几个关键信息？",
        "desc": "先看发布机构、会议层级、任务对象和后续执行入口。",
        "sources": "中国政府网 / 新华网 / 人民网",
        "read_time": "4分钟",
        "image": "/static/images/政策解读.png",
        "relation": "新闻关注者 / 办事群众 / 公共议题学习者",
        "summary": ["发布机构", "任务对象", "后续入口"],
        "sections": [
            {"heading": "发布机构决定权威性", "body": "先看信息来自哪一级机构，是会议通稿、政策文件，还是媒体解读。"},
            {"heading": "任务对象决定相关性", "body": "关注政策主要面向部门、地方、企业、学校、社区还是个人。"},
            {"heading": "后续执行才影响生活", "body": "真正影响个人体验的，通常是地方细则、办事入口和执行时间。"},
        ],
        "references": [
            {"title": "国务院政策文件与权威发布", "org": "中国政府网", "date": "公开发布", "url": "https://www.gov.cn/"},
            {"title": "时政新闻与权威报道", "org": "新华网", "date": "公开发布", "url": "https://www.news.cn/"},
        ],
        "is_today": True,
        "is_latest": True,
        "today_order": 3,
        "sort_order": 3,
    },
    {
        "article_id": "job",
        "category": "就业",
        "topic": "青年就业",
        "title": "刚毕业找工作，最近有哪些政策可能用得上？",
        "desc": "补贴、见习岗位和基层就业服务，是这一类信息里最值得先看的部分。",
        "sources": "人社部 / 中国政府网",
        "read_time": "3分钟",
        "image": "/static/images/就业.png",
        "relation": "毕业生 / 求职者 / 职场新人",
        "summary": ["就业补贴", "见习岗位", "申请入口"],
        "sections": [
            {"heading": "先找本地入口", "body": "刚毕业找工作，先去本地人社局、政务服务平台或学校就业中心，看有没有就业补贴、见习岗位和职业培训。"},
            {"heading": "条件比口号重要", "body": "能不能申请，通常卡在毕业时间、社保状态、户籍、材料和岗位类型。"},
            {"heading": "不要等自动发钱", "body": "把政策当成工具箱：符合就申请，不符合也不用焦虑。"},
        ],
        "references": [
            {"title": "高校毕业生等青年就业创业相关政策文件", "org": "中国政府网", "date": "公开发布", "url": "https://www.gov.cn/"},
            {"title": "就业服务与就业促进相关信息", "org": "人社部", "date": "公开发布", "url": "https://www.mohrss.gov.cn/"},
        ],
        "is_today": True,
        "is_latest": True,
        "today_order": 4,
        "sort_order": 4,
    },
    {
        "article_id": "housing",
        "category": "住房",
        "topic": "民生政策",
        "title": "租房和买房，哪些城市正在调整规则？",
        "desc": "公积金、保障性住房和租房补贴都值得留意，但一定要看本地细则。",
        "sources": "住建部 / 地方政府官网",
        "read_time": "4分钟",
        "image": "/static/images/住房.png",
        "relation": "租房人 / 新市民 / 公积金用户",
        "summary": ["租房补贴", "公积金", "保障住房"],
        "sections": [
            {"heading": "租住入口先看这里", "body": "如果你现在主要是租房，更实用的是租房补贴、人才公寓、保障性租赁住房和公积金租房提取。"},
            {"heading": "买房规则看本地", "body": "准备买房再看首付、贷款利率、公积金额度、户籍和社保要求。"},
            {"heading": "放宽不等于该买", "body": "政策放宽只是门槛变了，收入、现金流和居住计划仍然更关键。"},
        ],
        "references": [
            {"title": "住房和城乡建设相关政策信息", "org": "住建部", "date": "公开发布", "url": "https://www.mohurd.gov.cn/"}
        ],
        "is_today": True,
        "is_latest": True,
        "today_order": 5,
        "sort_order": 5,
    },
    {
        "article_id": "ai",
        "category": "科技",
        "topic": "科技产业",
        "title": "AI相关专业和就业，政策到底在鼓励什么？",
        "desc": "不只看大模型，也看产业应用、数据能力和真实岗位里的新技能。",
        "sources": "工信部 / 教育部",
        "read_time": "3分钟",
        "image": "/static/images/AI技术.png",
        "relation": "学生 / 转行者 / 科技从业者",
        "summary": ["产业应用", "技能训练", "岗位能力"],
        "sections": [
            {"heading": "重点在行业落地", "body": "AI政策不是只让大家做大模型，更大的方向是把AI放进制造、医疗、教育、交通和政务等真实场景。"},
            {"heading": "岗位不只算法岗", "body": "产品、运营、设计、数据分析、行业方案、测试，都可能因为AI多出新的能力要求。"},
            {"heading": "热词不能替代能力", "body": "更有用的是能拿AI工具解决一个具体问题，并说清楚过程和结果。"},
        ],
        "references": [
            {"title": "人工智能与数字经济相关政策信息", "org": "工信部", "date": "公开发布", "url": "https://www.miit.gov.cn/"},
            {"title": "高等教育专业与人才培养相关信息", "org": "教育部", "date": "公开发布", "url": "https://www.moe.gov.cn/"},
        ],
        "is_today": True,
        "is_latest": True,
        "today_order": 6,
        "sort_order": 6,
    },
    {
        "article_id": "medical",
        "category": "医保",
        "topic": "民生政策",
        "title": "医保支付改革，普通人需要担心什么？",
        "desc": "先分清基金支付、报销规则和异地就医入口，不要只看一个标题。",
        "sources": "国家医保局",
        "read_time": "4分钟",
        "image": "/static/images/医保社保.png",
        "relation": "本地居民 / 异地就医 / 家庭照护",
        "summary": ["基金支付", "报销规则", "异地就医"],
        "sections": [
            {"heading": "改的是支付方式", "body": "医保支付改革是在改变医保基金怎样给医院付钱，不只是个人能报多少。"},
            {"heading": "先查本地医保规则", "body": "普通人最该看本地报销目录、门诊统筹、异地就医和定点医院规则。"},
            {"heading": "不是简单少报销", "body": "不同病种、医院和地方方案，最后体感可能完全不一样。"},
        ],
        "references": [
            {"title": "医保支付方式改革相关政策信息", "org": "国家医保局", "date": "公开发布", "url": "https://www.nhsa.gov.cn/"}
        ],
        "is_today": True,
        "is_latest": False,
        "today_order": 7,
        "sort_order": 7,
    },
    {
        "article_id": "city-life",
        "category": "城市生活",
        "topic": "城市生活",
        "title": "城市公共服务调整，普通人该先看什么？",
        "desc": "交通、社区、教育、医疗等变化，重点看服务对象和本地入口。",
        "sources": "地方政府官网 / 政务服务平台",
        "read_time": "3分钟",
        "image": "/static/images/社会民生.png",
        "relation": "本地居民 / 新市民 / 社区用户",
        "summary": ["服务对象", "办理入口", "执行时间"],
        "sections": [
            {"heading": "先看服务对象", "body": "同一公共服务调整，可能只面向特定年龄、户籍、居住证或缴费状态的人群。"},
            {"heading": "入口比口号重要", "body": "办事入口通常在政务服务平台、街道社区或主管部门网站。"},
            {"heading": "执行时间决定体验", "body": "不少政策有过渡期，真正开始执行的日期要看地方通知。"},
        ],
        "references": [
            {"title": "地方政务服务公开信息", "org": "地方政府官网", "date": "公开发布", "url": "https://www.gov.cn/fuwu/"}
        ],
        "is_today": True,
        "is_latest": False,
        "today_order": 8,
        "sort_order": 8,
    },
]


FEATURES = [
    ("党和国家大事观察", "从会议、文件、部门分工看懂国家治理线索。", "会议部署 / 部门分工 / 地方落实", "/static/images/党和国家.png", 8, "党和国家"),
    ("经典文献入门", "党章、团章、共产党宣言、毛选、邓论等基础文本。", "党章 / 团章 / 宣言 / 毛选 / 邓论", "/static/images/共产党.png", 5, "共产党"),
    ("青年政策雷达", "找工作、见习、补贴和基层岗位。", "就业补贴 / 见习岗位 / 落户 / 租房", "/static/images/就业.png", 6, "就业"),
    ("AI和未来工作", "从产业政策看到新岗位和新技能。", "技能培训 / 行业应用 / 专业选择", "/static/images/AI技术.png", 5, "科技"),
]


PAGES = [
    (
        "legal",
        "隐私政策与用户协议",
        "平台规则、数据保存和内容边界说明",
        "2026-06-20",
        [
            {"title": "用户协议", "body": "欢迎使用见闻。你使用见闻，即表示你已阅读并同意本协议。"},
            {"title": "内容边界", "body": "平台内容用于公共信息学习和辅助理解，不构成法律、医疗、投资、就业、购房或其他专业建议。"},
            {"title": "隐私政策", "body": "登录后，见闻可能保存收藏、阅读历史、关注主题和问问记录，用于同步体验。"},
        ],
    ),
    (
        "sources",
        "内容来源说明",
        "见闻如何选择、整理和呈现公共信息",
        "2026-06-20",
        [
            {"title": "优先来源", "body": "优先参考政府官网、公共机构、权威媒体、公开政策文件和地方政务服务平台。"},
            {"title": "经典文献来源", "body": "经典文献第一版提供目录、简介和权威阅读入口；后续可在章节字段中补充全文。"},
            {"title": "AI辅助整理", "body": "AI用于提炼重点、解释背景和生成问答草稿，不是最终依据。"},
        ],
    ),
]


CLASSIC_BOOKS = [
    {
        "book_id": "party-constitution",
        "title": "中国共产党章程",
        "author": "中国共产党",
        "category": "党章团章",
        "description": "中国共产党的根本法规，集中规定党的性质、指导思想、组织制度、党员权利义务等基本内容。",
        "cover_image": "/static/images/共产党.png",
        "source_org": "共产党员网",
        "external_url": "https://www.12371.cn/special/zggcdzc/zggcdzcqw/",
        "is_featured": True,
        "sort_order": 1,
        "chapters": [
            ("总纲", "理解党的性质、指导思想、奋斗目标和基本路线。", "https://www.12371.cn/special/zggcdzc/zggcdzcqw/"),
            ("第一章 党员", "了解党员条件、义务、权利和发展党员要求。", "https://www.12371.cn/special/zggcdzc/zggcdzcqw/"),
            ("第二章 党的组织制度", "了解民主集中制和党的组织原则。", "https://www.12371.cn/special/zggcdzc/zggcdzcqw/"),
            ("第十一章 党徽党旗", "了解党徽党旗的基本规范。", "https://www.12371.cn/special/zggcdzc/zggcdzcqw/"),
        ],
    },
    {
        "book_id": "league-constitution",
        "title": "中国共产主义青年团章程",
        "author": "中国共产主义青年团",
        "category": "党章团章",
        "description": "共青团的基本章程，适合了解团的性质、组织制度、团员要求和青年工作基础。",
        "cover_image": "/static/images/公共生活.png",
        "source_org": "中国共青团网",
        "external_url": "https://www.gqt.org.cn/ccylmaterial/regulation/",
        "is_featured": True,
        "sort_order": 2,
        "chapters": [
            ("总则", "了解共青团性质、任务和行动指南。", "https://www.gqt.org.cn/ccylmaterial/regulation/"),
            ("第一章 团员", "了解团员条件、义务和权利。", "https://www.gqt.org.cn/ccylmaterial/regulation/"),
            ("第二章 团的组织制度", "了解团组织运行原则。", "https://www.gqt.org.cn/ccylmaterial/regulation/"),
            ("第八章 团旗、团徽、团歌", "了解团的标识和象征。", "https://www.gqt.org.cn/ccylmaterial/regulation/"),
        ],
    },
    {
        "book_id": "communist-manifesto",
        "title": "共产党宣言",
        "author": "马克思、恩格斯",
        "category": "马克思主义经典",
        "description": "马克思主义经典文本之一，适合作为理解科学社会主义和共产党人理论源流的入门读物。",
        "cover_image": "/static/images/政策解读.png",
        "source_org": "共产党员网",
        "external_url": "https://www.12371.cn/special/gcdxy/",
        "is_featured": True,
        "sort_order": 3,
        "chapters": [
            ("一、资产者和无产者", "从阶级关系和资本主义发展理解现代社会矛盾。", "https://www.12371.cn/special/gcdxy/"),
            ("二、无产者和共产党人", "理解共产党人与无产阶级运动的关系。", "https://www.12371.cn/special/gcdxy/"),
            ("三、社会主义的和共产主义的文献", "了解不同社会主义思潮的批判与区分。", "https://www.12371.cn/special/gcdxy/"),
            ("四、共产党人对各种反对党派的态度", "理解共产党人在不同政治条件下的策略。", "https://www.12371.cn/special/gcdxy/"),
        ],
    },
    {
        "book_id": "selected-works-mao",
        "title": "毛泽东选集",
        "author": "毛泽东",
        "category": "中国化时代化马克思主义",
        "description": "收录毛泽东同志在中国革命各时期的重要著作，适合按历史阶段和问题意识阅读。",
        "cover_image": "/static/images/共产党.png",
        "source_org": "共产党员网",
        "external_url": "https://www.12371.cn/special/mzdxj/dyj/",
        "is_featured": True,
        "sort_order": 4,
        "chapters": [
            ("第一卷", "第一次国内革命战争时期和土地革命战争时期的重要著作。", "https://www.12371.cn/special/mzdxj/dyj/"),
            ("第二卷", "抗日战争时期的重要著作。", "https://www.12371.cn/special/mzdxj/"),
            ("第三卷", "抗日战争后期的重要著作。", "https://www.12371.cn/special/mzdxj/"),
            ("第四卷", "解放战争时期的重要著作。", "https://www.12371.cn/special/mzdxj/"),
        ],
    },
    {
        "book_id": "selected-works-deng",
        "title": "邓小平文选",
        "author": "邓小平",
        "category": "中国化时代化马克思主义",
        "description": "理解邓小平理论的重要文本入口，适合结合改革开放和社会主义现代化建设历史阅读。",
        "cover_image": "/static/images/党和国家.png",
        "source_org": "共产党员网",
        "external_url": "https://www.12371.cn/special/dxpwx/d3j/",
        "is_featured": True,
        "sort_order": 5,
        "chapters": [
            ("第一卷", "收录早期革命和建设时期相关著述。", "https://www.12371.cn/special/dxpwx/"),
            ("第二卷", "收录改革开放前后重要讲话和文章。", "https://www.12371.cn/special/dxpwx/"),
            ("第三卷", "集中体现建设中国特色社会主义的重要论述。", "https://www.12371.cn/special/dxpwx/d3j/"),
        ],
    },
]


ASK_PROMPTS = [
    ("welcome", "直接问我一个政策、新闻、经典文献或现实问题。"),
    ("prompt", "最近有哪些党和国家大事值得关注？"),
    ("prompt", "党章应该从哪几部分开始读？"),
    ("prompt", "就业政策和年轻人有什么关系？"),
    ("followup", "讲简单点"),
    ("followup", "和我有关吗？"),
    ("followup", "依据在哪"),
]


ANSWER_RULES = [
    ("党章", "读党章可以先看总纲，再看党员、组织制度、党的干部、党的纪律等章节。第一遍重点抓党的性质、指导思想、组织原则和党员义务权利。", "共产党员网"),
    ("团章", "读团章可以先看总则、团员、团的组织制度和团干部等部分，重点理解共青团的性质、任务和青年组织运行规则。", "中国共青团网"),
    ("宣言", "读《共产党宣言》可以先看资产者和无产者、无产者和共产党人两部分，抓住资本主义社会分析和共产党人的政治立场。", "共产党员网、中文马克思主义文库"),
    ("毛选", "读《毛泽东选集》建议按历史阶段阅读，先了解每篇文章所处的革命实践背景，再看它回答的具体问题。", "共产党员网、求是网"),
    ("邓", "理解邓小平理论可以从《邓小平文选》第三卷入手，重点看改革开放、社会主义现代化建设和解放思想、实事求是等主题。", "共产党员网、学习强国"),
    ("就业", "可以先从本地人社部门、学校就业中心和政务服务平台三个入口查起，重点看补贴、见习、培训和基层岗位条件。", "中国政府网、人社部、地方政府官网"),
    ("租房", "租房相关政策优先查住建部门、住房保障平台和公积金中心。不同城市差异很大，要看本地执行细则。", "住建部、地方政府官网、公积金中心"),
    (None, "这个问题可以先拆成三层：事实是什么，来源在哪里，和你有什么关系。涉及政策或经典文献时，先看权威来源，再看背景和适用范围。", "中国政府网、共产党员网、相关主管部门官网"),
]


DAILY_QUOTES = [
    ("dq-001", "学而时习之，不亦说乎。", "《论语》", "孔子及其弟子", "classical", "修身", "学到的东西要反复实践，理解才会变深。", "看政策和新闻也需要持续复盘，不只看标题。"),
    ("dq-002", "知之为知之，不知为不知。", "《论语》", "孔子及其弟子", "classical", "求真", "知道就说知道，不确定就承认不确定。", "面对公共信息，先区分事实、解释和判断。"),
    ("dq-003", "民为贵，社稷次之，君为轻。", "《孟子》", "孟子及其弟子", "classical", "为民", "治理的核心应当把百姓放在最重要的位置。", "判断政策时，可以先看它怎样影响普通人。"),
    ("dq-004", "大学之道，在明明德。", "《大学》", "曾子相传", "classical", "修身", "学习和成长，首先是让道理变得清楚。", "复杂议题要先讲明白，再讨论立场。"),
    ("dq-005", "苟日新，日日新，又日新。", "《大学》", "曾子相传", "classical", "奋斗", "每天都能更新自己，长期就会形成改变。", "理解社会变化，需要持续跟进而不是一次看完。"),
    ("dq-006", "凡事预则立，不预则废。", "《礼记·中庸》", "佚名", "classical", "治理", "做事提前准备，才更容易站得住。", "政策落地常看配套细则和执行准备是否充分。"),
    ("dq-007", "天行健，君子以自强不息。", "《周易》", "佚名", "classical", "奋斗", "面对变化，人应保持主动和韧性。", "就业、学习和技能更新都需要长期投入。"),
    ("dq-008", "地势坤，君子以厚德载物。", "《周易》", "佚名", "classical", "修身", "有承载力的人，能包容复杂情况。", "公共议题往往有多方处境，需要耐心看全。"),
    ("dq-009", "路漫漫其修远兮。", "《离骚》", "屈原", "ancient", "求真", "追求正确方向，常常是一条长路。", "看清一个议题，需要不断查证和追问。"),
    ("dq-010", "纸上得来终觉浅。", "《冬夜读书示子聿》", "陆游", "ancient", "求真", "只看文字还不够，还要结合现实经验。", "政策是否有用，最终要看地方执行和个人条件。"),
    ("dq-011", "位卑未敢忘忧国。", "《病起书怀》", "陆游", "ancient", "为民", "普通人也可以关心公共事务。", "理解政策，是参与公共生活的基础能力。"),
    ("dq-012", "千磨万击还坚劲。", "《竹石》", "郑燮", "ancient", "奋斗", "经历反复考验，仍要保持稳定和韧性。", "面对就业和生活压力，先找可执行的入口。"),
    ("dq-013", "兼听则明，偏信则暗。", "《资治通鉴》", "司马光", "ancient", "治理", "多听多看，判断才不容易偏。", "新闻和政策解读应对照来源，避免只看单一说法。"),
    ("dq-014", "天下兴亡，匹夫有责。", "《日知录》相关思想", "顾炎武", "ancient", "为民", "公共事务和普通人的生活并不遥远。", "关注现实议题，是理解自己处境的一部分。"),
    ("dq-015", "实事求是。", "《改造我们的学习》", "毛泽东", "red", "求真", "判断问题要从事实出发，而不是先有结论。", "看政策新闻时，先核对原文和公开依据。"),
    ("dq-016", "没有调查，没有发言权。", "《反对本本主义》", "毛泽东", "red", "求真", "不了解实际情况，就不要轻易下判断。", "地方细则和真实办理流程常比标题更关键。"),
    ("dq-017", "为人民服务。", "《为人民服务》", "毛泽东", "red", "为民", "公共工作最终要回到人的需要。", "评估公共政策时，要看它解决了谁的问题。"),
    ("dq-018", "一切从实际出发。", "党的思想路线相关表述", "中国共产党", "red", "治理", "解决问题要看具体条件，不能只套概念。", "同一政策在不同城市，执行效果可能不同。"),
    ("dq-019", "世界是你们的，也是我们的。", "在莫斯科接见中国留学生时的讲话", "毛泽东", "red", "青年", "青年会承担越来越多现实责任。", "年轻人理解公共议题，是面向未来的准备。"),
    ("dq-020", "全世界无产者，联合起来！", "《共产党宣言》", "马克思、恩格斯", "manifesto", "奋斗", "共同处境中的人，需要形成共同力量。", "理解劳动、就业和社会保障，需要看群体处境。"),
    ("dq-021", "每个人的自由发展是一切人的自由发展的条件。", "《共产党宣言》", "马克思、恩格斯", "manifesto", "为民", "社会进步应让个人发展和共同发展相互支持。", "公共政策要兼顾个人机会和整体公平。"),
    ("dq-022", "过去的一切运动都是少数人的或者为少数人谋利益的运动。", "《共产党宣言》", "马克思、恩格斯", "manifesto", "治理", "经典文本关注多数人的现实处境。", "讨论公共议题时，要看利益影响的范围。"),
    ("dq-023", "共产党人不屑于隐瞒自己的观点和意图。", "《共产党宣言》", "马克思、恩格斯", "manifesto", "求真", "表达立场应清楚明确，接受公开检验。", "公共讨论需要把事实、依据和观点讲清楚。"),
    ("dq-024", "工人没有祖国。", "《共产党宣言》", "马克思、恩格斯", "manifesto", "青年", "这句话需放回文本语境理解，不能断章取义。", "阅读经典文本要结合背景和完整段落。"),
]
def _apply_fields(record: object, data: dict) -> None:
    for key, value in data.items():
        setattr(record, key, value)


def seed_content(db: Session) -> None:
    category_names = [name for name, _image, _is_priority in CATEGORIES]
    feature_titles = [title for title, _desc, _tags, _image, _count, _category_name in FEATURES]
    article_ids = [article["article_id"] for article in ARTICLES]
    db.query(ContentCategory).filter(~ContentCategory.name.in_(category_names)).delete(synchronize_session=False)
    db.query(ContentFeature).filter(~ContentFeature.title.in_(feature_titles)).delete(synchronize_session=False)
    db.query(ContentArticle).filter(~ContentArticle.article_id.in_(article_ids)).update(
        {"is_today": False, "is_latest": False},
        synchronize_session=False,
    )

    for index, (name, image, is_priority) in enumerate(CATEGORIES, start=1):
        record = db.query(ContentCategory).filter(ContentCategory.name == name).first()
        data = {"name": name, "image": image, "is_priority": is_priority, "sort_order": index}
        if record:
            _apply_fields(record, data)
        else:
            db.add(ContentCategory(**data))

    for article in ARTICLES:
        record = db.query(ContentArticle).filter(ContentArticle.article_id == article["article_id"]).first()
        if record:
            _apply_fields(record, article)
        else:
            db.add(ContentArticle(**article))

    for index, (title, desc, tags, image, count, category_name) in enumerate(FEATURES, start=1):
        record = db.query(ContentFeature).filter(ContentFeature.title == title).first()
        data = {
            "title": title,
            "desc": desc,
            "tags": tags,
            "image": image,
            "count": count,
            "category_name": category_name,
            "sort_order": index,
        }
        if record:
            _apply_fields(record, data)
        else:
            db.add(ContentFeature(**data))

    for page_key, title, subtitle, updated_label, sections in PAGES:
        record = db.query(ContentPage).filter(ContentPage.page_key == page_key).first()
        data = {
            "page_key": page_key,
            "title": title,
            "subtitle": subtitle,
            "updated_label": updated_label,
            "sections": sections,
        }
        if record:
            _apply_fields(record, data)
        else:
            db.add(ContentPage(**data))

    for book in CLASSIC_BOOKS:
        chapters = book["chapters"]
        book_data = {key: value for key, value in book.items() if key != "chapters"}
        record = db.query(ClassicBook).filter(ClassicBook.book_id == book["book_id"]).first()
        if record:
            _apply_fields(record, book_data)
        else:
            record = ClassicBook(**book_data)
            db.add(record)
        db.flush()

        if has_complete_qstheory_full_text(db, book["book_id"]):
            continue

        db.execute(
            sql_text(
                "UPDATE classic_book_chapters "
                "SET chapter_order = id + 100000 "
                "WHERE book_id = :book_id"
            ),
            {"book_id": book["book_id"]},
        )
        db.expire_all()
        db.flush()

        for order, (title, summary, external_url) in enumerate(chapters, start=1):
            chapter = (
                db.query(ClassicBookChapter)
                .filter(
                    ClassicBookChapter.book_id == book["book_id"],
                    ClassicBookChapter.title == title,
                )
                .first()
            )
            data = {
                "book_id": book["book_id"],
                "title": title,
                "chapter_order": order,
                "summary": summary,
                "external_url": external_url,
            }
            if chapter:
                _apply_fields(chapter, data)
            else:
                db.add(ClassicBookChapter(**data))

    db.query(AiPrompt).delete()
    for index, (prompt_type, text) in enumerate(ASK_PROMPTS, start=1):
        db.add(AiPrompt(prompt_type=prompt_type, text=text, sort_order=index))

    db.query(AiAnswerRule).delete()
    for index, (keyword, answer, sources) in enumerate(ANSWER_RULES, start=1):
        db.add(AiAnswerRule(keyword=keyword, answer=answer, sources=sources, sort_order=index))

    for index, (quote_id, text, source_title, source_author, source_type, theme, plain_explanation, today_connection) in enumerate(DAILY_QUOTES, start=1):
        record = db.query(DailyQuote).filter(DailyQuote.quote_id == quote_id).first()
        data = {
            "quote_id": quote_id,
            "text": text,
            "source_title": source_title,
            "source_author": source_author,
            "source_type": source_type,
            "theme": theme,
            "plain_explanation": plain_explanation,
            "today_connection": today_connection,
            "sort_order": index,
            "is_active": True,
        }
        if record:
            _apply_fields(record, data)
        else:
            db.add(DailyQuote(**data))
    db.commit()
    import_classic_full_texts(db)

