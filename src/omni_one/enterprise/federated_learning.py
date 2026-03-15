"""
Enterprise Federated Learning
Privacy-preserving distributed machine learning
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import hashlib
import json

class FederatedHub:
    """Federated learning coordinator for privacy-preserving AI"""

    def __init__(self):
        self.participants: Dict[str, Dict[str, Any]] = {}
        self.global_model = None
        self.rounds_completed = 0
        self.privacy_budget_used = 0.0
        self.federated_history = []

    def register_participant(self, participant_id: str, data_info: Dict[str, Any],
                           capabilities: List[str] = None) -> str:
        """Register a new participant in the federated learning network"""

        participant = {
            "id": participant_id,
            "data_info": data_info,
            "capabilities": capabilities or ["training", "inference"],
            "status": "active",
            "registered_at": datetime.now().isoformat(),
            "contribution_score": 0.0,
            "privacy_budget": 1.0,  # Start with full privacy budget
            "local_models": [],
            "performance_metrics": {}
        }

        self.participants[participant_id] = participant

        # Generate secure token for authentication
        token = hashlib.sha256(f"{participant_id}_{datetime.now().isoformat()}".encode()).hexdigest()[:16]

        return token

    def train_federated(self, dataset: str, model_config: Dict[str, Any] = None,
                       rounds: int = 10, min_participants: int = 3,
                       privacy_budget: float = 1.0) -> Dict[str, Any]:
        """Execute federated learning training"""

        start_time = datetime.now()

        # Validate minimum participants
        active_participants = [p for p in self.participants.values() if p["status"] == "active"]
        if len(active_participants) < min_participants:
            raise ValueError(f"Need at least {min_participants} active participants, only {len(active_participants)} available")

        # Initialize global model if not exists
        if self.global_model is None:
            self.global_model = self._initialize_global_model(model_config)

        training_results = []

        for round_num in range(rounds):
            round_start = datetime.now()

            # Select participants for this round
            selected_participants = self._select_participants(active_participants, round_num)

            # Distribute global model
            local_updates = []
            for participant in selected_participants:
                local_update = self._simulate_local_training(participant, self.global_model, dataset)
                local_updates.append(local_update)

            # Aggregate updates (Federated Averaging)
            global_update = self._federated_averaging(local_updates)

            # Update global model
            self.global_model = self._apply_update(self.global_model, global_update)

            # Evaluate global model
            round_accuracy = self._evaluate_global_model(self.global_model, dataset)

            # Update privacy budget
            self.privacy_budget_used += privacy_budget / rounds

            round_result = {
                "round": round_num + 1,
                "participants": len(selected_participants),
                "global_accuracy": round_accuracy,
                "computation_time": (datetime.now() - round_start).total_seconds(),
                "privacy_budget_used": self.privacy_budget_used
            }

            training_results.append(round_result)
            self.rounds_completed += 1

        total_time = (datetime.now() - start_time).total_seconds()

        result = {
            "global_model_accuracy": round_accuracy,
            "participants": len(active_participants),
            "rounds_completed": rounds,
            "total_computation_time": total_time,
            "privacy_budget_used": self.privacy_budget_used,
            "model_updated": True,
            "training_rounds": training_results,
            "final_model_hash": self._hash_model(self.global_model)
        }

        self.federated_history.append(result)
        return result

    def _initialize_global_model(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Initialize the global model"""
        if config is None:
            config = {"type": "neural_network", "layers": [784, 128, 64, 10]}

        # Mock model initialization
        model = {
            "config": config,
            "weights": [np.random.randn(*shape) for shape in config.get("layer_shapes", [(128, 784), (64, 128), (10, 64)])],
            "biases": [np.random.randn(shape[0]) for shape in config.get("layer_shapes", [(128,), (64,), (10,)])],
            "version": 1,
            "created_at": datetime.now().isoformat()
        }

        return model

    def _select_participants(self, participants: List[Dict[str, Any]], round_num: int) -> List[Dict[str, Any]]:
        """Select participants for federated learning round"""
        # Use round-robin selection with some randomness
        start_idx = round_num % len(participants)
        selected_count = min(len(participants), max(3, len(participants) // 2))

        selected = []
        for i in range(selected_count):
            idx = (start_idx + i) % len(participants)
            selected.append(participants[idx])

        return selected

    def _simulate_local_training(self, participant: Dict[str, Any], global_model: Dict[str, Any],
                               dataset: str) -> Dict[str, Any]:
        """Simulate local training on participant's device"""

        # Mock local training - in real implementation, this would be done on participant's device
        local_epochs = np.random.randint(1, 5)
        local_batch_size = 32

        # Simulate model update
        model_update = {
            "participant_id": participant["id"],
            "local_epochs": local_epochs,
            "batch_size": local_batch_size,
            "samples_used": np.random.randint(100, 1000),
            "weight_updates": [np.random.randn(*w.shape) * 0.01 for w in global_model["weights"]],
            "bias_updates": [np.random.randn(*b.shape) * 0.01 for b in global_model["biases"]],
            "training_loss": np.random.uniform(0.1, 0.5),
            "validation_accuracy": np.random.uniform(0.8, 0.95)
        }

        # Update participant contribution score
        participant["contribution_score"] += model_update["samples_used"] * model_update["validation_accuracy"]

        return model_update

    def _federated_averaging(self, local_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate local model updates using Federated Averaging"""

        if not local_updates:
            return {}

        # Average weight updates
        weight_updates = []
        for i, _ in enumerate(local_updates[0]["weight_updates"]):
            layer_updates = [update["weight_updates"][i] for update in local_updates]
            avg_update = np.mean(layer_updates, axis=0)
            weight_updates.append(avg_update)

        # Average bias updates
        bias_updates = []
        for i, _ in enumerate(local_updates[0]["bias_updates"]):
            layer_updates = [update["bias_updates"][i] for update in local_updates]
            avg_update = np.mean(layer_updates, axis=0)
            bias_updates.append(avg_update)

        return {
            "weight_updates": weight_updates,
            "bias_updates": bias_updates,
            "aggregation_method": "fedavg",
            "participating_clients": len(local_updates)
        }

    def _apply_update(self, global_model: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """Apply aggregated update to global model"""

        updated_model = global_model.copy()

        # Apply weight updates
        updated_weights = []
        for i, (weight, update_w) in enumerate(zip(global_model["weights"], update["weight_updates"])):
            new_weight = weight + update_w  # Simple addition (in practice, would use learning rate)
            updated_weights.append(new_weight)

        # Apply bias updates
        updated_biases = []
        for i, (bias, update_b) in enumerate(zip(global_model["biases"], update["bias_updates"])):
            new_bias = bias + update_b
            updated_biases.append(new_bias)

        updated_model["weights"] = updated_weights
        updated_model["biases"] = updated_biases
        updated_model["version"] += 1
        updated_model["updated_at"] = datetime.now().isoformat()

        return updated_model

    def _evaluate_global_model(self, model: Dict[str, Any], dataset: str) -> float:
        """Evaluate global model performance"""
        # Mock evaluation - in real implementation, would use test dataset
        return np.random.uniform(0.85, 0.98)

    def _hash_model(self, model: Dict[str, Any]) -> str:
        """Generate hash of model for integrity checking"""
        model_str = json.dumps({
            "weights": [w.tolist() for w in model["weights"]],
            "biases": [b.tolist() for b in model["biases"]],
            "version": model["version"]
        }, sort_keys=True)

        return hashlib.sha256(model_str.encode()).hexdigest()[:16]

    def get_federated_stats(self) -> Dict[str, Any]:
        """Get statistics about federated learning performance"""

        if not self.federated_history:
            return {"error": "No federated learning history available"}

        recent_runs = self.federated_history[-5:]  # Last 5 runs

        avg_accuracy = np.mean([r["global_model_accuracy"] for r in recent_runs])
        avg_participants = np.mean([r["participants"] for r in recent_runs])
        total_privacy_budget = sum(r["privacy_budget_used"] for r in recent_runs)

        return {
            "total_federated_runs": len(self.federated_history),
            "active_participants": len([p for p in self.participants.values() if p["status"] == "active"]),
            "average_accuracy": avg_accuracy,
            "average_participants_per_round": avg_participants,
            "total_privacy_budget_used": total_privacy_budget,
            "most_recent_accuracy": self.federated_history[-1]["global_model_accuracy"] if self.federated_history else None
        }

    def get_participant_contributions(self) -> List[Dict[str, Any]]:
        """Get contribution statistics for all participants"""

        contributions = []
        for participant in self.participants.values():
            contributions.append({
                "participant_id": participant["id"],
                "contribution_score": participant["contribution_score"],
                "privacy_budget_remaining": participant["privacy_budget"],
                "status": participant["status"],
                "data_info": participant["data_info"]
            })

        # Sort by contribution score
        contributions.sort(key=lambda x: x["contribution_score"], reverse=True)

        return contributions