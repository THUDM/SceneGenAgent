import re
from datasketch import MinHash, MinHashLSH

def remove_punctuation(input_string):
    punc = u'[\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300b．]'
    punc_en = r"[!\"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~\n]"
    st = re.sub(punc, '', input_string)
    st = re.sub(punc_en, "", st)
    return st

def get_minhash(text, num_perm=128):
    minhash = MinHash(num_perm=num_perm)
    for word in text.split():
        minhash.update(word.encode('utf-8'))
    return minhash

def minhash_task(text, num_perm=128):
    text = remove_punctuation(text).replace("\n", " ")
    minhash = get_minhash(text, num_perm)
    return minhash

class Hash:
    def __init__(self, threshold, num_perm) -> None:
        self.threshold = threshold
        self.num_perm = num_perm
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self.id_text_map = {}
    
    def can_insert(self, text):
        minhash = minhash_task(text, self.num_perm)
        query = self.lsh.query(minhash)
        if query:
            query = query[0]
            if self.id_text_map[query] not in text or self.id_text_map[query] == text:
                return False
        return True
    
    def insert(self, id, text, check=True):
        minhash = minhash_task(text, self.num_perm)
        if check and not self.can_insert(text):
            return False
        self.id_text_map[id] = text
        self.lsh.insert(id, minhash)
        return True
