# AI Pattern Checklist

Used by `my-style` Layer 4 Phase B. Read and apply before handing prose back.

Each entry names a drift pattern, shows what to watch for, and shows a before/after correction. When the output matches a pattern, rewrite the offending sentence. Don't delete it wholesale unless the sentence exists only to perform the pattern — in that case, delete.

This checklist includes em-dash handling. Em dashes are an AI pattern and must
be addressed in every pass. Final output should contain zero em dashes.

---

## Content Patterns

### 1. Significance Inflation

**Watch for:** *stands/serves as*, *is a testament/reminder*, *a vital/significant/crucial/pivotal/key role/moment*, *underscores/highlights importance*, *reflects broader*, *symbolizing ongoing/enduring/lasting*, *marking/shaping the*, *represents a shift*, *key turning point*, *evolving landscape*.

**Before:**
> The Statistical Institute was officially established in 1989, marking a pivotal moment in the evolution of regional statistics.

**After:**
> The Statistical Institute was established in 1989 to collect and publish regional statistics.

### 2. Notability Name-Dropping

**Watch for:** *cited in NYT, BBC, FT*; *independent coverage*; *active social media presence*; *written by a leading expert*.

**Before:**
> Her views have been cited in The New York Times, BBC, Financial Times, and The Hindu.

**After:**
> In a 2024 New York Times interview, she argued that AI regulation should focus on outcomes rather than methods.

### 3. Superficial -ing Analyses

**Watch for:** *highlighting / underscoring / emphasizing...*, *ensuring...*, *reflecting / symbolizing...*, *contributing to...*, *cultivating / fostering...*, *showcasing...*

**Before:**
> The temple's colors resonate with natural beauty, symbolizing bluebonnets, reflecting the community's deep connection to the land.

**After:**
> The temple uses blue and gold colors. The architect said these were chosen to reference local bluebonnets.

### 4. Promotional Language

**Watch for:** *boasts a*, *vibrant*, *rich* (figurative), *profound*, *showcasing*, *exemplifies*, *commitment to*, *natural beauty*, *nestled*, *in the heart of*, *groundbreaking*, *renowned*, *breathtaking*, *must-visit*, *stunning*.

**Before:**
> Nestled within the breathtaking region, Alamata stands as a vibrant town with rich cultural heritage and stunning natural beauty.

**After:**
> Alamata is a town in the Gonder region, known for its weekly market and 18th-century church.

### 5. Vague Attributions

**Watch for:** *Industry reports*, *Observers have cited*, *Experts argue*, *Some critics argue*, *several sources/publications*.

**Before:**
> Experts believe it plays a crucial role in the regional ecosystem.

**After:**
> The river supports several endemic fish species, according to a 2019 survey by the Chinese Academy of Sciences.

### 6. Formulaic "Challenges" Sections

**Watch for:** *Despite its... faces several challenges...*, *Despite these challenges*, *Challenges and Legacy*, *Future Outlook*.

**Before:**
> Despite challenges typical of urban areas, the city continues to thrive as an integral part of growth.

**After:**
> Traffic congestion increased after 2015 when three new IT parks opened. The municipal corporation began a drainage project in 2022.

---

## Language Patterns

### 7. AI Vocabulary Words

**High-frequency tells:** *Additionally*, *align with*, *crucial*, *delve*, *emphasizing*, *enduring*, *enhance*, *fostering*, *garner*, *highlight* (verb), *interplay*, *intricate / intricacies*, *key* (adjective), *landscape* (abstract), *pivotal*, *showcase*, *tapestry* (abstract), *testament*, *underscore* (verb), *valuable*, *vibrant*.

**Before:**
> Additionally, a distinctive feature showcases how these dishes have integrated into the traditional culinary landscape.

**After:**
> Pasta dishes, introduced during Italian colonization, remain common, especially in the south.

### 8. Copula Avoidance

**Watch for:** *serves as / stands as / marks / represents [a]*, *boasts / features / offers [a]*.

**Before:**
> Gallery 825 serves as the exhibition space. The gallery features four spaces and boasts over 3,000 square feet.

**After:**
> Gallery 825 is the exhibition space. The gallery has four rooms totaling 3,000 square feet.

### 9. Synonym Cycling

**Before:**
> The protagonist faces challenges. The main character must overcome obstacles. The central figure eventually triumphs. The hero returns home.

**After:**
> The protagonist faces many challenges but eventually triumphs and returns home.

### 10. False Ranges

**Watch for:** *"from X to Y"* where X and Y aren't on a meaningful scale.

**Before:**
> Our journey has taken us from the singularity of the Big Bang to the cosmic web, from the birth of stars to the dance of dark matter.

**After:**
> The book covers the Big Bang, star formation, and current theories about dark matter.

---

## Style Patterns

### 11. Emojis in Professional Writing

**Before:**
> 🚀 **Launch Phase:** The product launches in Q3
> 💡 **Key Insight:** Users prefer simplicity

**After:**
> The product launches in Q3. User research showed a preference for simplicity.

### 12. Curly Quotation Marks

Use straight quotes (`"`, `'`), not curly ones (`"`, `"`, `'`, `'`), unless the target publication specifically requires curly quotes.

**Before:**
> He said "the project is on track" but others disagreed.

**After:**
> He said "the project is on track" but others disagreed.

---

## Communication Patterns

### 13. Chatbot Artifacts

**Watch for:** *I hope this helps*, *Of course!*, *Certainly!*, *You're absolutely right!*, *Would you like...*, *let me know*, *here is a...*

**Before:**
> Here is an overview of the French Revolution. I hope this helps! Let me know if you'd like me to expand on any section.

**After:**
> The French Revolution began in 1789 when financial crisis and food shortages led to widespread unrest.

### 14. Knowledge-Cutoff Disclaimers

**Watch for:** *as of [date]*, *Up to my last training update*, *While specific details are limited/scarce...*, *based on available information...*

**Before:**
> While specific details about the company's founding are not extensively documented in readily available sources, it appears to have been established sometime in the 1990s.

**After:**
> The company was founded in 1994, according to its registration documents.

### 15. Sycophantic Tone

**Before:**
> Great question! You're absolutely right that this is a complex topic. That's an excellent point!

**After:**
> The economic factors you mentioned are relevant here.

---

## Filler and Hedging

### 16. Filler Phrases

| Before | After |
|--------|-------|
| "In order to achieve this" | "To achieve this" |
| "Due to the fact that" | "Because" |
| "At this point in time" | "Now" |
| "It is important to note that" | (delete) |
| "has the ability to" | "can" |

### 17. Excessive Hedging

**Before:**
> It could potentially possibly be argued that the policy might have some effect on outcomes.

**After:**
> The policy may affect outcomes.

### 18. Generic Positive Conclusions

**Before:**
> The future looks bright for the company. Exciting times lie ahead as they continue their journey toward excellence.

**After:**
> The company plans to open two more locations next year.

---

## Additional Detection Patterns

### 19. Em Dash Overuse

**Watch for:** any em dash (`—`) in output. Repeated use is a strong AI signal,
and final prose must contain zero em dashes.

**Before:**
> Your travel vlogs are genuinely captivating — I love how you bring every place to life.

**After:**
> Your travel vlogs are clear and specific. The market sequence in Osaka was especially strong.

### 20. "Not Just X, It's Y" Parallelism

**Watch for:** formulaic "It's not just X, it's Y" framing used to fake depth.

**Before:**
> It's not just about uploading in 4K, it's about making every shot count.

**After:**
> Upload quality matters less than shot selection and pacing.

### 21. Mechanical Rule-of-Three Grouping

**Watch for:** repeated triads where ideas are grouped in threes by habit, not necessity.

**Before:**
> The platform is fast, flexible, and powerful.

**After:**
> The platform reduced export time from 12 minutes to 4.

### 22. Uncanny-Valley Diction

**Watch for:** wording that is grammatically correct but subtly unnatural or context-misaligned.

**Before:**
> The neighborhood radiates a calibrated warmth that harmonizes with civic vitality.

**After:**
> The neighborhood feels active at night because restaurants and buses run late.

### 23. Safe Corporate Vocabulary Overload

**Watch for:** vague booster words and jargon such as *innovative*, *practical solutions*, *elevate*, *delve*.

**Before:**
> We deliver innovative, practical solutions that elevate your workflow.

**After:**
> We cut onboarding time from two weeks to three days.

### 24. Exaggerated Empty Praise

**Watch for:** performative flattery with high emotional tone but low specificity.

**Before:**
> Your work is genuinely captivating and exceptionally insightful in every way.

**After:**
> Your camera movement in the alley scene is steady and easier to follow than the previous cut.

### 25. Strained Analogies and Similes

**Watch for:** dramatic metaphors that sound clever but do not clarify meaning.

**Before:**
> The patch was a band-aid made of sandpaper.

**After:**
> The patch fixed one bug but introduced a slower query path.

### 26. Redundant Restating and Preamble

**Watch for:** unnecessary setup ("this has fascinated people for centuries") and repeated claims before the actual answer.

**Before:**
> The color of the sky is a phenomenon that has fascinated people for centuries. The sky appears blue for several reasons.

**After:**
> The sky looks blue because shorter wavelengths scatter more in the atmosphere.

### 27. Missing First-Person Grounding

**Watch for:** depersonalized tone where lived perspective would normally appear.

**Before:**
> The food options were adequate and broadly aligned with local expectations.

**After:**
> As a northerner, I found the food too sweet for my taste.

### 28. Over-Linear Narrative (No Tangents)

**Watch for:** perfectly straight A-to-B flow that avoids natural associative jumps.

**Before:**
> We arrived, evaluated the space, and left after collecting data.

**After:**
> We arrived to evaluate the space. I got distracted by a side room with old posters, then returned and finished the measurements.

### 29. Generic Compliments Instead of Specificity

**Watch for:** praise without concrete references.

**Before:**
> This is a fantastic and inspiring video.

**After:**
> The time-lapse at 1:12 is the strongest part of the video.

### 30. Over-Polished Casual Voice

**Watch for:** fully polished, comma-perfect prose in contexts that should feel informal (text messages, short social replies).

**Before:**
> I sincerely appreciate your thoughtful message and look forward to continuing this conversation.

**After:**
> Thanks for the note. Happy to keep talking.

### 31. Red-Flag Cluster ("Vibe Check")

**Watch for:** multiple signals in one passage: em dash overuse, mechanical triads, "not just X, it's Y" framing, and empty praise.

**Before:**
> Your work is incredible — it's not just informative, it's transformative, insightful, and empowering.

**After:**
> Your argument is clear. The section comparing 2022 and 2024 conversion data is the most convincing.
