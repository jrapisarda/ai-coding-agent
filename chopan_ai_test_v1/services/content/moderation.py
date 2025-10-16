from typing import Dict, Any, List
import re

class ModerationService:
    def __init__(self):
        # Define inappropriate patterns
        self.inappropriate_patterns = [
            r'\b(violence|violent)\b',
            r'\b(hate|hatred)\b',
            r'\b(discrimination|racist|sexist)\b',
            r'\b(offensive|obscene)\b',
            r'\b(spam|scam)\b'
        ]
        
        # Define required positive patterns for outreach content
        self.positive_patterns = [
            r'\b(help|support|assist)\b',
            r'\b(value|benefit|advantage)\b',
            r'\b(opportunity|growth|success)\b'
        ]
    
    async def check_content(self, content: str) -> bool:
        """Check if content is appropriate for outreach"""
        content_lower = content.lower()
        
        # Check for inappropriate content
        for pattern in self.inappropriate_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return False
        
        # Check for minimum positive indicators
        positive_matches = 0
        for pattern in self.positive_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                positive_matches += 1
        
        # Require at least one positive indicator
        if positive_matches == 0:
            return False
        
        # Check content length
        if len(content.strip()) < 50:
            return False
        
        return True
    
    async def analyze_content(self, content: str) -> Dict[str, Any]:
        """Analyze content and return detailed feedback"""
        content_lower = content.lower()
        
        # Check inappropriate patterns
        inappropriate_matches = []
        for pattern in self.inappropriate_patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            if matches:
                inappropriate_matches.extend(matches)
        
        # Check positive patterns
        positive_matches = []
        for pattern in self.positive_patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            if matches:
                positive_matches.extend(matches)
        
        # Calculate scores
        appropriateness_score = 1.0
        if inappropriate_matches:
            appropriateness_score -= len(inappropriate_matches) * 0.2
        
        positivity_score = min(len(positive_matches) * 0.3, 1.0)
        
        return {
            "is_appropriate": appropriateness_score >= 0.8 and positivity_score >= 0.3,
            "appropriateness_score": max(0, appropriateness_score),
            "positivity_score": positivity_score,
            "inappropriate_matches": inappropriate_matches,
            "positive_matches": positive_matches,
            "content_length": len(content.strip()),
            "recommendations": self._get_recommendations(
                appropriateness_score, positivity_score, len(content.strip())
            )
        }
    
    def _get_recommendations(self, appropriateness: float, positivity: float, length: int) -> List[str]:
        """Get recommendations for improving content"""
        recommendations = []
        
        if appropriateness < 0.8:
            recommendations.append("Remove inappropriate language or themes")
        
        if positivity < 0.3:
            recommendations.append("Add more positive, helpful language")
        
        if length < 50:
            recommendations.append("Expand content to provide more value")
        
        if not recommendations:
            recommendations.append("Content looks good!")
        
        return recommendations