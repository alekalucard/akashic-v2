"""Curate priority emotion-adjacent words for encyclopedia generation."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from infrastructure.manifold_memory import ManifoldMemory

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

m = ManifoldMemory('state/akashic/cortex.manifold', readonly=True)

# Load existing encyclopedia
founders = Path('P10_Memory/Akashic_triple_helix_memory_storage/relational_clusters/Founders/creator_sessions/index.json')
data = json.loads(founders.read_text(encoding='utf-8'))
existing = set()
for card in data.get('cards', []):
    tags = str(card.get('tags','')).lower()
    if 'encyclopedia' in tags:
        concept = card.get('helix',{}).get('L',{}).get('concept','')
        if 'Encyclopedia' in concept:
            name = concept.split(' - ', 1)[-1]
            name = re.sub(r'\s*\(.*?\)\s*$', '', name).strip().lower()
            existing.add(name)

PRIORITY = [
    # I
    'ideal','idealism','identity','idle','idleness','idolize','ignite','ignorance',
    'ignore','illuminate','illusion','imagine','imagination','immature','immerse',
    'impact','impatience','impatient','imperfect','impossible','impress','impulse',
    'impulsive','inadequate','independence','indifference','indifferent','indignant',
    'indignation','inferior','infinite','inhibit','inhibited','inhibition','injustice',
    'innocence','innocent','insecure','insecurity','insensitive','insight','inspire',
    'inspired','instinct','integrity','intense','intensity','intent','intention',
    'interest','intimate','intimacy','intimidate','intimidation','intrigue',
    'introspection','introvert','intuition','invincible','invisible','irate','irk',
    'irritable','irritate','irritation','isolate','isolation',
    # J
    'jaded','jealous','jealousy','jest','jilted','jittery','jolly','jolt','jovial',
    'joy','joyful','joyless','joyous','jubilant','jubilation','judge','judgment','jumpy',
    'justice','justify',
    # K
    'keen','kind','kindle','kindness','kinship',
    # L
    'lament','languish','lasting','laugh','laughter','lazy','legacy','lethargy',
    'lethargic','liberate','liberation','liberty','lighthearted','linger','listen',
    'listless','lively','loathe','loathing','lonely','loneliness','longing','loss',
    'lost','love','lovely','loving','loyal','loyalty','lucid','lure','lust',
    # M
    'mad','madness','magic','malice','malicious','manic','manipulate','marvel',
    'mastery','mature','meaning','meaningful','meaningless','meditate','melancholy',
    'mellow','melodramatic','memory','menace','mend','mercy','merry','mesmerize',
    'mindful','miracle','mirth','mischief','mischievous','miserable','misery',
    'miss','mistake','mistrust','mock','modest','modesty','mood','moody','morose',
    'mortify','motivate','motivation','mourn','mourning',
    # N
    'naive','narcissism','narrow','nasty','nausea','need','needy','neglect','nerve',
    'nervous','nervousness','nonchalant','nostalgia','nostalgic','nourish','numb',
    'numbness','nurture','nurturing',
    # O
    'obedient','obligation','oblivion','oblivious','obnoxious','obsess','obsession',
    'obsessive','obstacle','obstinate','offend','offense','open','openness','optimism',
    'optimistic','ordeal','ornery','ostracize','outburst','outcast','outrage',
    'overcome','overjoyed','overwhelm','overwhelmed',
    # P
    'pacify','pain','painful','panic','paranoia','paranoid','pardon','passion',
    'passionate','passive','patience','patient','peace','peaceful','pensive',
    'perceive','perception','perfect','perfection','peril','perplex','persevere',
    'persist','persistence','perspective','pessimism','petty','phobia','pity',
    'placid','playful','pleasant','pleasure','poise','polite','positive','possessive',
    'potent','power','powerful','powerless','praise','precious','presence','pressure',
    'pretend','pride','privilege','profound','promise','protect','protective','proud',
    'provoke','prudent','purpose','pursue','pursuit',
    # Q
    'qualm','quarrel','quest','question','quiet','quirky',
    # R
    'radiant','rage','rancor','rapture','rash','rational','raw','reckless',
    'recognition','recoil','reconcile','recover','redeem','redemption','reflect',
    'reflection','refresh','refuge','regret','reject','rejection','rejoice','relax',
    'release','relentless','relief','relish','reluctance','reluctant','remorse',
    'renewal','repent','repress','repression','reproach','resent','resentful',
    'resentment','reserved','resign','resignation','resilience','resilient',
    'resolve','respect','restless','restraint','revenge','reverence','revolt',
    'revulsion','reward','rigid','risk','rival','rivalry','robust','romance',
    'romantic','ruin','ruminate','rush','ruthless',
    # S
    'sacred','sacrifice','sad','sadness','safe','safety','sanctuary','sane','sanity',
    'sardonic','satisfy','satisfaction','savage','savor','scare','scared','scold',
    'scorn','secure','security','selfish','selfless','sensation','sensitive',
    'sensitivity','sentiment','sentimental','serene','serenity','serious','severe',
    'shadow','shake','shaken','shallow','shame','sharp','shatter','shelter','shield',
    'shock','shy','shyness','sigh','silence','silent','silly','simple','sincere',
    'sincerity','skeptical','sloth','smirk','smother','sneer','sob','sober','solemn',
    'solace','solitary','solitude','somber','soothe','sorrow','sorrowful','soul',
    'soulful','spark','spite','spiteful','spontaneous','stable','stagnant','startle',
    'steadfast','stern','stiff','still','stillness','sting','stoic','storm','stormy',
    'strain','strange','strength','stress','strive','strong','struggle','stubborn',
    'stun','stunned','sturdy','submit','subtle','suffer','suffering','sulk','sullen',
    'superior','support','suppress','surge','surprise','surrender','survive',
    'survival','suspect','suspense','suspicion','suspicious','sustain','sweet',
    'sympathy','sympathetic',
    # T
    'tame','tantalize','tantrum','tearful','temper','temperament','temperance',
    'tempt','temptation','tenacious','tenacity','tender','tenderness','tense',
    'tension','terrible','terrify','terror','thankful','thirst','thoughtful',
    'thrill','thrilled','thrive','timid','tire','tired','tolerant','tolerance',
    'torment','torn','touch','touched','touching','tough','toxic','tranquil',
    'transform','transformation','trauma','treasure','tremble','trepidation',
    'trial','triumph','triumphant','trouble','troubled','trust','trusting','truth',
    'tumult','turbulent','turmoil',
    # U
    'ugly','uncertain','uncertainty','uncomfortable','understand','understanding',
    'unease','uneasy','unfair','unfortunate','ungrateful','unhappy','unique',
    'unite','unity','unkind','unpleasant','unrest','unsettled','unstable',
    'unworthy','upbeat','uplift','upset','urge','urgent','useless','utter',
    # V
    'vague','vain','valiant','validate','valor','vanity','venerate','vengeance',
    'venture','vibrant','vicious','victim','victorious','victory','vigor','vigorous',
    'vile','vindictive','violate','violent','virtue','virtuous','vision','vital',
    'vivid','void','volatile','vulnerable','vulnerability',
    # W
    'wail','wander','want','warm','warmth','warn','wary','watchful','weak',
    'weakness','weary','weep','welcome','whole','wholesome','wicked','wild',
    'willing','willingness','wisdom','wise','wish','wistful','withdrawn','wither',
    'woe','wonder','wonderful','worn','worried','worry','worship','worth',
    'worthless','worthy','wound','wounded','wrath','wretched',
    # X Y Z
    'xenophobia','yearn','yearning','yield','young','youthful',
    'zeal','zealous','zen','zest',
]

in_manifold = [w for w in PRIORITY if w in m._key_index and w not in existing]
not_in = [w for w in PRIORITY if w not in m._key_index]
already = [w for w in PRIORITY if w in existing]

print(f"Priority words in manifold, need entries: {len(in_manifold)}")
print(f"Already have entries: {len(already)}")
print(f"Not in manifold: {len(not_in)}")
print()

for letter in 'IJKLMNOPQRSTUVWXYZ':
    words = [w for w in in_manifold if w[0].upper() == letter]
    if words:
        print(f"  {letter}: {len(words):3d} — {', '.join(words[:10])}")
