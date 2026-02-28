"""
DragonScope Model Registry

MLflow-inspired model lifecycle management with semantic versioning,
artifact storage, and stage transitions.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Set, Tuple
import threading
import pickle

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModelStage(Enum):
    """Model lifecycle stages."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class ModelType(Enum):
    """Types of financial ML models."""
    PRICE_PREDICTION = "price_prediction"
    REGIME_DETECTION = "regime_detection"
    ANOMALY_DETECTION = "anomaly_detection"
    FACTOR_MODEL = "factor_model"
    RISK_MODEL = "risk_model"
    PORTFOLIO_OPTIMIZATION = "portfolio_optimization"
    SENTIMENT_ANALYSIS = "sentiment_analysis"


class AlgorithmType(Enum):
    """Supported ML algorithms."""
    # Gradient Boosting
    LIGHTGBM = "lightgbm"
    XGBOOST = "xgboost"
    CATBOOST = "catboost"
    
    # Neural Networks
    LSTM = "lstm"
    GRU = "gru"
    TRANSFORMER = "transformer"
    TFT = "temporal_fusion_transformer"
    NBEATS = "nbeats"
    
    # Traditional ML
    RANDOM_FOREST = "random_forest"
    SVM = "svm"
    LOGISTIC_REGRESSION = "logistic_regression"
    LINEAR_REGRESSION = "linear_regression"
    
    # Unsupervised
    HMM = "hidden_markov_model"
    GMM = "gaussian_mixture_model"
    ISOLATION_FOREST = "isolation_forest"
    AUTOENCODER = "autoencoder"
    
    # Statistical
    PROPHET = "prophet"
    ARIMA = "arima"
    VAR = "vector_autoregression"


@dataclass
class ModelSignature:
    """Model input/output signature."""
    inputs: Dict[str, str]  # name -> type
    outputs: Dict[str, str]  # name -> type
    
    def to_dict(self) -> Dict[str, Any]:
        return {"inputs": self.inputs, "outputs": self.outputs}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelSignature:
        return cls(inputs=data["inputs"], outputs=data["outputs"])


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    # Common metrics
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Regression metrics
    mse: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None
    mape: Optional[float] = None
    r2: Optional[float] = None
    
    # Classification metrics
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    auc_roc: Optional[float] = None
    log_loss: Optional[float] = None
    
    # Financial metrics
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    calmar_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    
    # Custom metrics
    custom: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v.isoformat() if isinstance(v, datetime) else v
            for k, v in asdict(self).items()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelMetrics:
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class ModelArtifact:
    """Model artifact metadata."""
    name: str
    path: str
    size_bytes: int
    checksum: str
    content_type: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "content_type": self.content_type,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ModelVersion:
    """A specific version of a model."""
    name: str
    version: str  # Semantic version
    model_type: ModelType
    algorithm: AlgorithmType
    
    # Source
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    training_run_id: Optional[str] = None
    
    # Metadata
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "unknown"
    
    # Model artifacts
    signature: Optional[ModelSignature] = None
    artifacts: List[ModelArtifact] = field(default_factory=list)
    
    # Metrics
    metrics: ModelMetrics = field(default_factory=ModelMetrics)
    
    # Lifecycle
    stage: ModelStage = ModelStage.DEVELOPMENT
    stage_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Dependencies
    python_version: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)  # package -> version
    feature_dependencies: List[str] = field(default_factory=list)
    
    # Lineage
    parent_version: Optional[str] = None
    datasets: List[str] = field(default_factory=list)
    
    @property
    def full_name(self) -> str:
        """Get fully qualified model name."""
        return f"{self.name}:{self.version}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "model_type": self.model_type.value,
            "algorithm": self.algorithm.value,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "training_run_id": self.training_run_id,
            "description": self.description,
            "tags": self.tags,
            "params": self.params,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "signature": self.signature.to_dict() if self.signature else None,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "metrics": self.metrics.to_dict(),
            "stage": self.stage.value,
            "stage_history": self.stage_history,
            "python_version": self.python_version,
            "dependencies": self.dependencies,
            "feature_dependencies": self.feature_dependencies,
            "parent_version": self.parent_version,
            "datasets": self.datasets,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelVersion:
        data = data.copy()
        data["model_type"] = ModelType(data["model_type"])
        data["algorithm"] = AlgorithmType(data["algorithm"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["stage"] = ModelStage(data["stage"])
        
        if data.get("signature"):
            data["signature"] = ModelSignature.from_dict(data["signature"])
        
        if data.get("artifacts"):
            data["artifacts"] = [
                ModelArtifact(
                    name=a["name"],
                    path=a["path"],
                    size_bytes=a["size_bytes"],
                    checksum=a["checksum"],
                    content_type=a["content_type"],
                    created_at=datetime.fromisoformat(a["created_at"]),
                )
                for a in data["artifacts"]
            ]
        
        if data.get("metrics"):
            data["metrics"] = ModelMetrics.from_dict(data["metrics"])
        else:
            data["metrics"] = ModelMetrics()
        
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ArtifactStore:
    """Storage backend for model artifacts."""
    
    def __init__(self, base_path: str):
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
    
    def _compute_checksum(self, filepath: Path) -> str:
        """Compute MD5 checksum of file."""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def save_artifact(
        self,
        model_name: str,
        version: str,
        artifact_name: str,
        source_path: str,
    ) -> ModelArtifact:
        """Save an artifact to the store."""
        model_dir = self._base_path / model_name / version
        model_dir.mkdir(parents=True, exist_ok=True)
        
        dest_path = model_dir / artifact_name
        source = Path(source_path)
        
        if source.is_dir():
            # Archive directory
            archive_path = dest_path.with_suffix(".zip")
            shutil.make_archive(str(dest_path), "zip", source)
            dest_path = archive_path
        else:
            shutil.copy2(source_path, dest_path)
        
        checksum = self._compute_checksum(dest_path)
        
        return ModelArtifact(
            name=artifact_name,
            path=str(dest_path),
            size_bytes=dest_path.stat().st_size,
            checksum=checksum,
            content_type=self._get_content_type(dest_path),
        )
    
    def load_artifact(
        self,
        model_name: str,
        version: str,
        artifact_name: str,
        dest_dir: Optional[str] = None,
    ) -> str:
        """Load an artifact from the store."""
        artifact_path = self._base_path / model_name / version / artifact_name
        
        if not artifact_path.exists():
            # Try with zip extension
            artifact_path = artifact_path.with_suffix(".zip")
        
        if dest_dir:
            dest = Path(dest_dir) / artifact_name
            if artifact_path.suffix == ".zip":
                shutil.unpack_archive(artifact_path, dest)
            else:
                shutil.copy2(artifact_path, dest)
            return str(dest)
        
        return str(artifact_path)
    
    def delete_artifact(self, model_name: str, version: str, artifact_name: str) -> None:
        """Delete an artifact."""
        artifact_path = self._base_path / model_name / version / artifact_name
        if artifact_path.exists():
            if artifact_path.is_dir():
                shutil.rmtree(artifact_path)
            else:
                artifact_path.unlink()
    
    def list_artifacts(self, model_name: str, version: str) -> List[str]:
        """List all artifacts for a model version."""
        model_dir = self._base_path / model_name / version
        if not model_dir.exists():
            return []
        return [f.name for f in model_dir.iterdir()]
    
    def _get_content_type(self, path: Path) -> str:
        """Get content type from file extension."""
        suffix = path.suffix.lower()
        types = {
            ".pkl": "application/octet-stream",
            ".pickle": "application/octet-stream",
            ".json": "application/json",
            ".yaml": "application/yaml",
            ".yml": "application/yaml",
            ".py": "text/python",
            ".zip": "application/zip",
            ".onnx": "application/onnx",
            ".h5": "application/hdf5",
        }
        return types.get(suffix, "application/octet-stream")


class ModelRegistry:
    """
    Model Registry for managing ML model lifecycle.
    
    Features:
    - Semantic versioning (MAJOR.MINOR.PATCH)
    - Stage transitions (dev → staging → prod → archived)
    - Artifact storage and retrieval
    - Model lineage tracking
    - Signature validation
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        artifact_store: Optional[ArtifactStore] = None,
    ):
        self._storage_path = Path(storage_path or ".model_registry")
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._artifact_store = artifact_store or ArtifactStore(
            str(self._storage_path / "artifacts")
        )
        
        self._models: Dict[str, List[ModelVersion]] = {}
        self._lock = threading.RLock()
        
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load registry from disk."""
        registry_file = self._storage_path / "registry.json"
        if registry_file.exists():
            with open(registry_file) as f:
                data = json.load(f)
                for name, versions in data.items():
                    self._models[name] = [
                        ModelVersion.from_dict(v) for v in versions
                    ]
    
    def _save_registry(self) -> None:
        """Save registry to disk."""
        registry_file = self._storage_path / "registry.json"
        with open(registry_file, "w") as f:
            data = {
                name: [v.to_dict() for v in versions]
                for name, versions in self._models.items()
            }
            json.dump(data, f, indent=2, default=str)
    
    def create_model(
        self,
        name: str,
        model_type: ModelType,
        algorithm: AlgorithmType,
        description: str = "",
    ) -> str:
        """
        Create a new model entry in the registry.
        
        Returns:
            Initial version string (1.0.0)
        """
        with self._lock:
            if name not in self._models:
                self._models[name] = []
            
            # Check if model exists
            if any(v for v in self._models[name] if v.stage != ModelStage.ARCHIVED):
                raise ValueError(f"Model {name} already exists")
            
            version = ModelVersion(
                name=name,
                version="1.0.0",
                model_type=model_type,
                algorithm=algorithm,
                description=description,
            )
            
            self._models[name].append(version)
            self._save_registry()
            
            logger.info(f"Created model {name} v1.0.0")
            return "1.0.0"
    
    def register_version(
        self,
        name: str,
        model_type: ModelType,
        algorithm: AlgorithmType,
        model_object: Any,
        metrics: Optional[ModelMetrics] = None,
        params: Optional[Dict[str, Any]] = None,
        signature: Optional[ModelSignature] = None,
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
        git_commit: Optional[str] = None,
        increment: str = "minor",  # major, minor, patch
    ) -> ModelVersion:
        """
        Register a new model version.
        
        Args:
            name: Model name
            model_type: Type of model
            algorithm: Algorithm used
            model_object: The trained model (will be pickled)
            metrics: Performance metrics
            params: Model hyperparameters
            signature: Input/output signature
            description: Version description
            tags: Metadata tags
            git_commit: Associated git commit
            increment: Version increment type
        
        Returns:
            Registered ModelVersion
        """
        with self._lock:
            if name not in self._models:
                self._models[name] = []
            
            # Compute new version
            existing_versions = [v.version for v in self._models[name]]
            new_version = self._bump_version(existing_versions, increment)
            
            # Create version object
            version = ModelVersion(
                name=name,
                version=new_version,
                model_type=model_type,
                algorithm=algorithm,
                description=description,
                tags=tags or {},
                params=params or {},
                signature=signature,
                metrics=metrics or ModelMetrics(),
                git_commit=git_commit,
                created_by=os.environ.get("USER", "unknown"),
                python_version=f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
            )
            
            # Save model artifact
            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                pickle.dump(model_object, f)
                temp_path = f.name
            
            try:
                artifact = self._artifact_store.save_artifact(
                    name, new_version, "model.pkl", temp_path
                )
                version.artifacts.append(artifact)
            finally:
                os.unlink(temp_path)
            
            self._models[name].append(version)
            self._save_registry()
            
            logger.info(f"Registered {name} v{new_version}")
            return version
    
    def _bump_version(
        self,
        existing_versions: List[str],
        increment: str,
    ) -> str:
        """Compute next semantic version."""
        if not existing_versions:
            return "1.0.0"
        
        # Parse versions
        parsed = []
        for v in existing_versions:
            try:
                parts = v.split(".")
                parsed.append(tuple(int(p) for p in parts))
            except ValueError:
                continue
        
        if not parsed:
            return "1.0.0"
        
        latest = max(parsed)
        major, minor, patch = latest
        
        if increment == "major":
            return f"{major + 1}.0.0"
        elif increment == "minor":
            return f"{major}.{minor + 1}.0"
        else:  # patch
            return f"{major}.{minor}.{patch + 1}"
    
    def transition_stage(
        self,
        name: str,
        version: str,
        stage: ModelStage,
        comment: str = "",
    ) -> ModelVersion:
        """
        Transition a model to a new stage.
        
        Args:
            name: Model name
            version: Version string
            stage: Target stage
            comment: Transition comment
        
        Returns:
            Updated ModelVersion
        """
        with self._lock:
            version_obj = self.get_version(name, version)
            if not version_obj:
                raise ValueError(f"Model {name} v{version} not found")
            
            old_stage = version_obj.stage
            version_obj.stage = stage
            
            version_obj.stage_history.append({
                "from": old_stage.value,
                "to": stage.value,
                "timestamp": datetime.utcnow().isoformat(),
                "comment": comment,
            })
            
            self._save_registry()
            
            logger.info(f"Transitioned {name} v{version}: {old_stage.value} -> {stage.value}")
            return version_obj
    
    def get_version(
        self,
        name: str,
        version: Optional[str] = None,
        stage: Optional[ModelStage] = None,
    ) -> Optional[ModelVersion]:
        """
        Get a specific model version.
        
        Args:
            name: Model name
            version: Specific version or None for latest
            stage: Filter by stage
        
        Returns:
            ModelVersion or None
        """
        if name not in self._models:
            return None
        
        versions = self._models[name]
        
        if stage:
            versions = [v for v in versions if v.stage == stage]
        
        if not versions:
            return None
        
        if version:
            return next((v for v in versions if v.version == version), None)
        
        # Return latest by version
        return max(versions, key=lambda v: tuple(int(x) for x in v.version.split(".")))
    
    def get_production_model(self, name: str) -> Optional[ModelVersion]:
        """Get the current production model."""
        return self.get_version(name, stage=ModelStage.PRODUCTION)
    
    def load_model(
        self,
        name: str,
        version: Optional[str] = None,
        stage: Optional[ModelStage] = None,
    ) -> Any:
        """
        Load a model artifact.
        
        Args:
            name: Model name
            version: Specific version
            stage: Load by stage (e.g., PRODUCTION)
        
        Returns:
            Deserialized model object
        """
        version_obj = self.get_version(name, version, stage)
        if not version_obj:
            raise ValueError(f"Model {name} not found")
        
        # Find model artifact
        model_artifact = next(
            (a for a in version_obj.artifacts if a.name == "model.pkl"),
            None
        )
        
        if not model_artifact:
            raise ValueError(f"No model artifact found for {name} v{version_obj.version}")
        
        # Load and verify checksum
        with open(model_artifact.path, "rb") as f:
            data = f.read()
            
        checksum = hashlib.md5(data).hexdigest()
        if checksum != model_artifact.checksum:
            raise ValueError("Model artifact checksum mismatch - possible corruption")
        
        return pickle.loads(data)
    
    def list_models(
        self,
        model_type: Optional[ModelType] = None,
        stage: Optional[ModelStage] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """List registered models with optional filtering."""
        results = []
        
        for name, versions in self._models.items():
            # Check if any version matches filters
            matching = versions
            
            if model_type:
                matching = [v for v in matching if v.model_type == model_type]
            
            if stage:
                matching = [v for v in matching if v.stage == stage]
            
            if tags:
                matching = [
                    v for v in matching
                    if all(v.tags.get(k) == v for k, v in tags.items())
                ]
            
            if matching:
                results.append(name)
        
        return results
    
    def list_versions(
        self,
        name: str,
        stage: Optional[ModelStage] = None,
    ) -> List[ModelVersion]:
        """List all versions of a model."""
        if name not in self._models:
            return []
        
        versions = self._models[name]
        
        if stage:
            versions = [v for v in versions if v.stage == stage]
        
        return sorted(
            versions,
            key=lambda v: tuple(int(x) for x in v.version.split(".")),
            reverse=True
        )
    
    def add_artifact(
        self,
        name: str,
        version: str,
        artifact_path: str,
        artifact_name: Optional[str] = None,
    ) -> ModelArtifact:
        """Add an artifact to a model version."""
        with self._lock:
            version_obj = self.get_version(name, version)
            if not version_obj:
                raise ValueError(f"Model {name} v{version} not found")
            
            artifact_name = artifact_name or Path(artifact_path).name
            
            artifact = self._artifact_store.save_artifact(
                name, version, artifact_name, artifact_path
            )
            
            version_obj.artifacts.append(artifact)
            self._save_registry()
            
            return artifact
    
    def delete_version(self, name: str, version: str) -> None:
        """Delete a model version."""
        with self._lock:
            if name not in self._models:
                return
            
            self._models[name] = [
                v for v in self._models[name] if v.version != version
            ]
            
            # Clean up artifacts
            for artifact_name in self._artifact_store.list_artifacts(name, version):
                self._artifact_store.delete_artifact(name, version, artifact_name)
            
            self._save_registry()
            
            logger.info(f"Deleted {name} v{version}")
    
    def compare_versions(
        self,
        name: str,
        version1: str,
        version2: str,
    ) -> Dict[str, Any]:
        """Compare two model versions."""
        v1 = self.get_version(name, version1)
        v2 = self.get_version(name, version2)
        
        if not v1 or not v2:
            raise ValueError("One or both versions not found")
        
        return {
            "version1": v1.to_dict(),
            "version2": v2.to_dict(),
            "metric_differences": {
                k: getattr(v2.metrics, k) - getattr(v1.metrics, k)
                for k in ["rmse", "mae", "accuracy", "sharpe_ratio"]
                if getattr(v1.metrics, k) is not None and getattr(v2.metrics, k) is not None
            },
            "param_differences": {
                k: (v1.params.get(k), v2.params.get(k))
                for k in set(v1.params.keys()) | set(v2.params.keys())
                if v1.params.get(k) != v2.params.get(k)
            },
        }
    
    def get_model_lineage(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get full lineage for a model."""
        version_obj = self.get_version(name, version)
        if not version_obj:
            raise ValueError(f"Model {name} not found")
        
        return {
            "model": version_obj.to_dict(),
            "parent": (
                self.get_version(name, version_obj.parent_version).to_dict()
                if version_obj.parent_version else None
            ),
            "children": [
                v.to_dict() for v in self._models.get(name, [])
                if v.parent_version == version_obj.version
            ],
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def get_default_registry(storage_path: Optional[str] = None) -> ModelRegistry:
    """Get or create the default model registry."""
    return ModelRegistry(storage_path=storage_path)
