"""Gradient-free explanation maps read from intermediate ONNX tensors.

Two families are supported, discovered from the graph itself:

* CNN with global average pooling and a linear head (ResNet, EfficientNet). For this head
  Grad-CAM's channel weights equal the classifier weights divided by the number of positions, so
  Grad-CAM reduces exactly to W[c] . F (Zhou et al. 2016; Selvaraju et al. 2017). No gradients are
  needed and the map is class-specific. At load time the head is replayed in NumPy and must
  reproduce the graph logits, otherwise the method is disabled.
* Vision Transformer with a CLS token. Attention rollout (Abnar and Zuidema 2020) multiplies the
  head-averaged attention matrices of every layer, with the residual connection added as identity.
  The map is not class-specific: it shows which patches the CLS token drew on.

Both maps show model behaviour, not lesion boundaries. When neither family is found, the caller
falls back to occlusion sensitivity.
"""
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

Method = Literal['grad-cam', 'attention-rollout']


@dataclass(frozen=True)
class Explainer:
    method: Method
    logits_output: str
    outputs: tuple[str, ...]
    embedding_output: str
    weight: np.ndarray | None = field(default=None, compare=False)
    bias: np.ndarray | None = field(default=None, compare=False)

    def heatmap(self, values: dict[str, np.ndarray], target: int) -> np.ndarray:
        if self.method == 'grad-cam':
            return grad_cam(values[self.outputs[0]], self.weight, target)
        return attention_rollout([values[name] for name in self.outputs])

    def embedding(self, values: dict[str, np.ndarray]) -> np.ndarray:
        tensor = np.asarray(values[self.embedding_output], np.float64)
        vector = tensor.mean(axis=(2, 3))[0] if tensor.ndim == 4 else tensor.reshape(tensor.shape[0], -1)[0]
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm <= 0:
            raise ValueError('The image embedding is not finite.')
        return vector / norm


def _initializer(model, name: str) -> np.ndarray | None:
    from onnx import numpy_helper
    for item in model.graph.initializer:
        if item.name == name:
            return numpy_helper.to_array(item).astype(np.float64)
    return None


def _attribute(node, name: str, default=None):
    from onnx import helper
    for item in node.attribute:
        if item.name == name:
            return helper.get_attribute_value(item)
    return default


def discover(model) -> Explainer | None:
    """Find a supported explanation path in a loaded onnx.ModelProto, or return None."""
    graph = model.graph
    if not graph.output:
        return None
    logits = graph.output[0].name
    producers = {output: node for node in graph.node for output in node.output}
    head = producers.get(logits)
    # CNN: logits = Gemm(Flatten(GlobalAveragePool(F)), W, b).
    if head is not None and head.op_type == 'Gemm' and len(head.input) >= 2:
        flatten = producers.get(head.input[0])
        pool = producers.get(flatten.input[0]) if flatten is not None and flatten.op_type == 'Flatten' else None
        weight = _initializer(model, head.input[1])
        bias = _initializer(model, head.input[2]) if len(head.input) > 2 else None
        if pool is not None and pool.op_type == 'GlobalAveragePool' and weight is not None and weight.ndim == 2:
            if _attribute(head, 'transA', 0) == 0 and _attribute(head, 'alpha', 1.0) == 1.0 and _attribute(head, 'beta', 1.0) == 1.0:
                if _attribute(head, 'transB', 0) == 0:
                    weight = weight.T
                bias = np.zeros(weight.shape[0]) if bias is None else bias.reshape(-1)
                return Explainer('grad-cam', logits, (pool.input[0],), pool.input[0], weight, bias)
    # Vision Transformer: one attention Softmax per encoder layer; the classifier reads the CLS token.
    attention = tuple(node.output[0] for node in graph.node if node.op_type == 'Softmax' and _attribute(node, 'axis', -1) in (-1, 3)
                      and 'attention' in node.output[0].lower())
    cls = next((node.output[0] for node in graph.node if node.op_type == 'Gather' and _attribute(node, 'axis', 0) == 1
                and getattr(producers.get(node.input[0]), 'op_type', '') == 'LayerNormalization'), None)
    if 2 <= len(attention) <= 48 and cls is not None:
        return Explainer('attention-rollout', logits, attention, cls)
    return None


def augment(raw: bytes) -> tuple[bytes, Explainer] | None:
    """Expose the tensors an explainer needs as extra graph outputs, entirely in memory."""
    try:
        import onnx
    except ImportError:
        return None
    try:
        model = onnx.load_from_string(raw)
        explainer = discover(model)
        if explainer is None:
            return None
        existing = {output.name for output in model.graph.output}
        for name in dict.fromkeys((*explainer.outputs, explainer.embedding_output)):
            if name not in existing:
                model.graph.output.append(onnx.ValueInfoProto(name=name))
        return model.SerializeToString(), explainer
    except Exception:
        return None


def grad_cam(features: np.ndarray, weight: np.ndarray, target: int) -> np.ndarray:
    """Class activation map for a global-average-pool + linear head (equal to Grad-CAM for this head)."""
    features = np.asarray(features, np.float64)
    if features.ndim != 4 or features.shape[0] != 1 or weight.shape[1] != features.shape[1]:
        raise ValueError('Unsupported feature map for Grad-CAM.')
    return np.maximum(np.tensordot(weight[target], features[0], axes=(0, 0)), 0)


def replay_head(features: np.ndarray, weight: np.ndarray, bias: np.ndarray) -> np.ndarray:
    return weight @ np.asarray(features, np.float64)[0].mean(axis=(1, 2)) + bias


def attention_rollout(attentions: list[np.ndarray]) -> np.ndarray:
    size = None
    result = None
    for attention in attentions:
        matrix = np.asarray(attention, np.float64)
        if matrix.ndim != 4 or matrix.shape[0] != 1 or matrix.shape[-1] != matrix.shape[-2]:
            raise ValueError('Unsupported attention tensor.')
        matrix = matrix[0].mean(axis=0)
        size = size or matrix.shape[-1]
        if matrix.shape[-1] != size:
            raise ValueError('Attention tensors disagree in size.')
        matrix = .5 * matrix + .5 * np.eye(size)
        matrix /= matrix.sum(axis=-1, keepdims=True)
        result = matrix if result is None else matrix @ result
    if result is None:
        raise ValueError('No attention tensors were returned.')
    grid = int(round(np.sqrt(size - 1)))
    if grid * grid != size - 1:
        raise ValueError('Attention tokens do not form a square patch grid with one CLS token.')
    cls = result[0, 1:].reshape(grid, grid)
    return cls - cls.min()


def normalized(heatmap: np.ndarray) -> list[float]:
    values = np.asarray(heatmap, np.float64)
    if not np.isfinite(values).all():
        raise ValueError('The heatmap is not finite.')
    peak = float(values.max())
    values = values / peak if peak > 1e-12 else np.zeros_like(values)
    return [round(float(item), 4) for item in np.clip(values, 0, 1).reshape(-1)]
