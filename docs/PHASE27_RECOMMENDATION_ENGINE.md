# ZYNOVA VIDEO — RECOMMENDATION ENGINE
**Deterministic & Explainable Video Ranking Specification**  

---

## 1. Recommendation Algorithm Specification

Zynova Video utilizes a modular, deterministic ranking algorithm designed for high throughput and explainability without black-box ML latency:

$$\text{Score} = \frac{\text{likes} \times 2.0 + \text{comments} \times 3.0 + \text{views} \times 0.5 + \text{sub\_boost}}{(\text{age\_in\_hours} + 2.0)^{1.3}}$$

Where:
- **`sub_boost`**: $+25.0$ if the viewer is currently subscribed to the video's creator channel.
- **`age_in_hours`**: Hours elapsed since `created_at` timestamp in UTC.
- **Decay Factor ($1.3$)**: Balances evergreen popular content with emerging uploads.

---

## 2. Hard Security & Privacy Filtering

Before scoring:
1. **Visibility Exclusion**: Private and unlisted videos are strictly excluded from the recommendation candidate pool.
2. **Mutual Block Isolation**: If the viewer and creator have a block relationship, the candidate video is pruned.
3. **Category Filtering**: Optional category filters narrow candidates to specific viewer interests.
