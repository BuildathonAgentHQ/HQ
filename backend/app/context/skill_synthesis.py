"""
backend/app/context/skill_synthesis.py — Agent Skill Synthesizer.

Manages storing, retrieving, and updating learned agent skills.
Connects to Databricks Vector Search if enabled, or falls back to an
in-memory scikit-learn TF-IDF vectorizer for development and sprint purposes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.app.config import Settings
from shared.schemas import SkillRecipe

logger = logging.getLogger(__name__)


class SkillSynthesizer:
    """Manages long-term learning of agent skills and routines."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.use_databricks = getattr(settings, "USE_DATABRICKS", False)

        # In-memory vector store fallback
        # Stores tuples of (task_description: str, recipe: SkillRecipe)
        self._memory_store: list[tuple[str, SkillRecipe]] = []
        
        if not self.use_databricks:
            logger.info("Databricks Vector Search disabled. Falling back to in-memory TF-IDF vectorizer.")
            self._vectorizer = TfidfVectorizer(stop_words="english")
            self._is_fitted = False
            self._corpus: list[str] = []
            self._vectors: Any = None
        else:
            logger.info("Configured to use Databricks Vector Search (implementation stubbed).")
            # Stub for real databricks client initialization would go here

    async def store_skill(self, task_description: str, steps: list[str], success: bool) -> None:
        """Vectorize and store a successful execution trace as a new skill."""
        if not success:
            logger.debug(f"Skipping skill storage: task was not successful ('{task_description}')")
            return

        now = datetime.now(timezone.utc)
        
        # We assign a synthetic name based on the task description or just a timestamp
        skill_name = f"Skill_{now.strftime('%Y%m%d_%H%M%S')}"
        
        recipe = SkillRecipe(
            name=skill_name,
            steps=steps,
            success_rate=1.0,
            last_used=now,
        )

        if self.use_databricks:
            # Stub out real Databricks Vector Search logic
            logger.debug(f"Databricks: Storing skill '{skill_name}'")
            return

        # In-memory fallback
        self._memory_store.append((task_description, recipe))
        self._corpus.append(task_description)
        
        # Refit the vectorizer on the full corpus
        self._vectors = self._vectorizer.fit_transform(self._corpus)
        self._is_fitted = True
        logger.info(f"Stored local skill '{skill_name}'. Memory store size: {len(self._memory_store)}")

    async def find_similar_skills(self, task_description: str, top_k: int = 3) -> list[SkillRecipe]:
        """Find the most similar recorded skills for a given task description."""
        if self.use_databricks:
            # Stub out real Databricks Vector Search query
            return []

        if not self._is_fitted or not self._memory_store:
            return []

        try:
            # Vectorize the query using the fitted model
            query_vector = self._vectorizer.transform([task_description])
            
            # Compute cosine similarities between the query and all stored documents
            similarities = cosine_similarity(query_vector, self._vectors)[0]
            
            # Get indices of the top_k most similar documents
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            results: list[SkillRecipe] = []
            for idx in top_indices:
                score = similarities[idx]
                # Optional: exclude skills below a certain similarity threshold (e.g. 0.1)
                if score > 0.05:
                    recipe = self._memory_store[idx][1]
                    # Update last_used to now on retrieval
                    recipe.last_used = datetime.now(timezone.utc)
                    results.append(recipe)
                    
            return results
        except Exception as e:
            logger.error(f"Error querying local vector store: {e}")
            return []

    async def update_skill_success_rate(self, skill_name: str, succeeded: bool) -> None:
        """Update the running success rate for an existing skill using exponential moving average."""
        if self.use_databricks:
            # Stub out real Databricks Vector Search update
            return
            
        for i, (desc, recipe) in enumerate(self._memory_store):
            if recipe.name == skill_name:
                # Simple exponential moving average (alpha = 0.2)
                alpha = 0.2
                current_rate = recipe.success_rate
                new_outcome = 1.0 if succeeded else 0.0
                new_rate = (alpha * new_outcome) + ((1.0 - alpha) * current_rate)
                
                recipe.success_rate = min(max(new_rate, 0.0), 1.0) # Clamp between 0 and 1
                recipe.last_used = datetime.now(timezone.utc)
                self._memory_store[i] = (desc, recipe)
                
                logger.info(f"Updated success rate for skill '{skill_name}' to {recipe.success_rate:.2f}")
                return
                
        logger.warning(f"Skill '{skill_name}' not found for success rate update.")
