"""Install a fingerprinted sentence encoder for local evidence retrieval, not diagnosis."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'Xenova/all-MiniLM-L6-v2'
REVISION = '751bff37182d3f1213fa05d7196b954e230abad9'
WEIGHTS_SHA = 'afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1'
TOKENIZER_GIT_BLOB = 'c17ed520ed8438736732a54957a69306b8822215'


def obtain(directory, remote, local, sha256=None, git_blob=None):
    target = directory / local
    if target.exists():
        raw = target.read_bytes()
    else:
        url = f'https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{remote}'
        request = urllib.request.Request(url, headers={'User-Agent': 'HumanTwin-Research/1.0'})
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read(80 * 1024 * 1024)
    actual = hashlib.sha256(raw).hexdigest()
    if sha256 and actual != sha256:
        raise ValueError('Downloaded encoder fingerprint mismatch.')
    if git_blob and hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != git_blob:
        raise ValueError('Downloaded tokenizer fingerprint mismatch.')
    temporary = target.with_suffix(target.suffix + '.partial')
    temporary.write_bytes(raw)
    temporary.replace(target)
    return actual


def main():
    directory = ROOT / 'models/cancer-knowledge'
    directory.mkdir(parents=True, exist_ok=True)
    model_hash = obtain(directory, 'onnx/model_quantized.onnx', 'model.onnx', sha256=WEIGHTS_SHA)
    tokenizer_hash = obtain(directory, 'tokenizer.json', 'tokenizer.json', git_blob=TOKENIZER_GIT_BLOB)
    obtain(directory, 'README.md', 'SOURCE-README.md')
    manifest = {'format': 'humantwin-cancer-encoder-v1', 'model_version': 'minilm-l6-q8-' + REVISION[:8],
                'model_sha256': model_hash, 'tokenizer_sha256': tokenizer_hash,
                'source_url': f'https://huggingface.co/{REPOSITORY}/tree/{REVISION}',
                'license': 'Apache-2.0', 'pooling': 'attention-masked-mean-l2-normalized',
                'maximum_tokens': 256, 'embedding_dimensions': 384, 'clinical_validation': False}
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Installed real local semantic encoder:', manifest['model_version'])
    print('Model SHA-256:', model_hash)


if __name__ == '__main__':
    main()
