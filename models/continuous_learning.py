import json
import os
from datetime import datetime
from typing import Dict, Any, List
from model_router import ModelRouter

class ContinuousLearning:
    def __init__(self, model_router: ModelRouter, feedback_file: str = 'learning_data.json'):
        self.model_router = model_router
        self.feedback_file = feedback_file
        self.feedback_data = self._load_feedback()

    def _load_feedback(self) -> List[Dict[str, Any]]:
        """Load existing feedback data."""
        if os.path.exists(self.feedback_file):
            with open(self.feedback_file, 'r') as f:
                return json.load(f)
        return []

    def _save_feedback(self):
        """Save feedback data."""
        with open(self.feedback_file, 'w') as f:
            json.dump(self.feedback_data, f, indent=2)

    def collect_feedback(self, query: str, response: str, rating: int, user_feedback: str = None):
        """Collect user feedback on responses."""
        feedback_entry = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'response': response,
            'rating': rating,  # 1-5 scale
            'user_feedback': user_feedback,
            'model_used': 'current'
        }
        self.feedback_data.append(feedback_entry)
        self._save_feedback()

    def analyze_feedback(self) -> Dict[str, Any]:
        """Analyze feedback patterns."""
        if not self.feedback_data:
            return {'message': 'No feedback data available'}

        ratings = [f['rating'] for f in self.feedback_data]
        avg_rating = sum(ratings) / len(ratings)

        # Identify common issues
        low_ratings = [f for f in self.feedback_data if f['rating'] <= 2]
        issues = []
        for feedback in low_ratings:
            if feedback['user_feedback']:
                issues.append(feedback['user_feedback'])

        return {
            'total_feedback': len(self.feedback_data),
            'average_rating': avg_rating,
            'low_rating_count': len(low_ratings),
            'common_issues': issues[:5],  # Top 5 issues
            'improvement_suggestions': self._generate_improvements(avg_rating, issues)
        }

    def _generate_improvements(self, avg_rating: float, issues: List[str]) -> List[str]:
        """Generate improvement suggestions based on feedback."""
        if avg_rating > 4.0:
            return ["Continue excellent performance", "Consider advanced features"]
        elif avg_rating > 3.0:
            return ["Focus on accuracy improvements", "Enhance response clarity"]
        else:
            suggestions = ["Major quality improvements needed"]
            if issues:
                suggestions.append("Address common user complaints")
            return suggestions

    def retrain_models(self):
        """Trigger model retraining based on feedback (placeholder for future implementation)."""
        # In a real system, this would:
        # 1. Prepare training data from feedback
        # 2. Fine-tune models
        # 3. Validate improvements
        # 4. Deploy updated models
        print("Model retraining triggered (placeholder implementation)")
        return {'status': 'retraining_scheduled'}

    def get_learning_insights(self) -> Dict[str, Any]:
        """Get insights from learning data."""
        analysis = self.analyze_feedback()
        return {
            'feedback_analysis': analysis,
            'learning_recommendations': self._generate_learning_recommendations(analysis),
            'data_points': len(self.feedback_data)
        }

    def _generate_learning_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations for system improvement."""
        recommendations = []
        if analysis['average_rating'] < 3.5:
            recommendations.append("Implement feedback-driven prompt engineering")
        if analysis['low_rating_count'] > len(self.feedback_data) * 0.2:
            recommendations.append("Review and improve core response quality")
        recommendations.append("Continue collecting user feedback for iterative improvement")
        return recommendations