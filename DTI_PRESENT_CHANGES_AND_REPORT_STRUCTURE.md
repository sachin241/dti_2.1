# DTI-2.1 Present Changes and Final Report Structure

## A) Present Changes in DTI-2.1

This section captures the latest implemented updates in the Smart Multi-Platform Price Tracker (DTI-2.1).

### 1. Core Feature Updates
- Added multi-platform tracking support for Amazon.in, Flipkart, Myntra, and Snapdeal.
- Improved URL-based platform auto-detection and scraper selector handling.
- Added delete tracking flow from the dashboard/track page.
- Added profile page support with avatar upload workflow.

### 2. Backend and Data Layer Updates
- Enhanced SQLite schema and helper methods for safer tracking workflows.
- Improved product and alert-related data handling for scheduler/email flows.
- Refined database access patterns using context-safe operations.

### 3. Scheduler and Alerting Updates
- Configured recurring background checks (6-hour interval) using APScheduler.
- Added duplicate-alert prevention logic to avoid repeated notification spam.
- Improved alert conditions based on target-price comparison.

### 4. Email and Notification Updates
- Updated HTML email formatting for clearer and branded alerts.
- Improved environment-variable based credential handling.
- Removed insecure hardcoded credential patterns.

### 5. UI/UX and Template Updates
- Upgraded UI to a premium dark theme ("Ember Noir" style).
- Improved responsive behavior with mobile hamburger navigation.
- Updated dashboard, compare, analytics, login, track, and base templates.
- Added reusable chatbot widget template.

### 6. AI and Chat Integration
- Integrated a sitewide AI chatbot interface.
- Added Gemini API key-based configuration path for assistant responses.
- Included helper script for chat API integration updates.

### 7. Security and Reliability Improvements
- Added password hashing for safer credential storage.
- Strengthened startup/runtime robustness for static directory and config handling.
- Added sensitive file ignore protections in `.gitignore`.

### 8. Documentation and Project Artifacts
- Updated README with v2.1 highlights and implementation notes.
- Added/updated project documentation:
  - `PROJECT_CHRONICLE.md`
  - `PROJECT_RESEARCH.md`
  - `DTI_FINAL_REPORT.md`

---

## B) Final DTI Project Report Structure

This section defines the required structure for the final DTI project report.

## 1. Title Page
Include:
- Project title
- Team members
- Guide/Faculty name
- Department/College
- Academic year

## 2. Abstract
- Brief summary of the project in 150-200 words.
- Mention purpose, approach, key outcomes, and conclusion.

## 3. Introduction
Include:
- Background of the problem/pattern
- Importance of the project

## 4. Problem Statement
- Clear, concise, and focused description of the exact problem being solved.

## 5. Literature Review
- Study and analysis of existing solutions.
- Mention strengths, limitations, and research gap.

## 6. Design Thinking Process
Explain all stages:
1. **Empathize** - understanding users and pain points
2. **Define** - problem definition from user insights
3. **Ideate** - idea generation and option selection
4. **Prototype** - model/prototype creation
5. **Test** - evaluation and iteration based on feedback

## 7. Proposed Solution
- Detailed explanation of the proposed solution.
- Key modules, functionality, and user value.

## 8. System Design
Include:
- Architecture diagram
- Flow charts
- Block diagrams

## 9. Implementation
- Tools, techniques, technologies, and deployment approach.

## 10. Testing and Results
- Testing methods used (unit/integration/UAT/performance).
- Outcomes, observations, and result summary.

## 11. Impact and Benefits
Include:
- Social benefits
- Economic benefits
- Technical improvements

## 12. Future Enhancements
- Practical next-step improvements and scalability ideas.

## 13. Conclusion
- Final summary of the project, achievements, and architecture impact.

## 14. References
- Books, journals, websites, standards, and documentation sources used.
- Follow one citation style consistently (APA/MLA/IEEE).

---

## C) Suggested Submission Checklist

- Title page details are complete and verified.
- Abstract is within 150-200 words.
- Design Thinking stages are clearly mapped to your project.
- Architecture/flow/block diagrams are attached and readable.
- Testing section includes measurable outcomes.
- References are consistent and properly formatted.

