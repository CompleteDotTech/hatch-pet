# Complete character state index

Catalog 1.0.0: 416 canonical definitions and 408 aliases. All records below are definitions, not generated artwork. Use `python scripts/hatch.py states show <id>` for full poses, generation constraints, anatomy, timing and review requirements.

Search with `python scripts/hatch.py states search "term"`; filter with `--category`, `--family`, `--tag` or `--archetype`. Alias selectors resolve to one canonical record.

## Neutral, Idle and Ambient (34)

Resting postures, attention and personality-specific ambient behavior.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `idle` | Calm resting, breathing and occasional tiny blink. | 4 / loop | `neutral`, `resting-idle` |
| `relaxed-idle` | A loosely weighted idle with visibly relaxed joints or contour. | 4 / loop | — |
| `alert-idle` | Remain on watch while stationary and ready to react. | 4 / loop | — |
| `sleepy-idle` | Resist dozing while remaining mostly awake. | 4 / loop | — |
| `breathing` | Isolated slow expansion and contraction of the established body. | 4 / loop | — |
| `blinking` | One complete regular eyelid closure during stillness. | 4 / once | `blink` |
| `double-blinking` | Two closely spaced eyelid closures as a distinct alertness accent. | 5 / once | `double-blink` |
| `looking-around` | Survey several directions with deliberate head or body turns. | 4 / loop | `look-around` |
| `looking-left` | Turn attention left while keeping the body planted. | 4 / once | `look-left` |
| `looking-right` | Turn attention right while keeping the body planted. | 4 / once | `look-right` |
| `looking-up` | Raise attention toward a point above the character. | 4 / once | `look-up` |
| `looking-down` | Lower attention toward a point near the character's base. | 4 / once | `look-down` |
| `looking-behind` | Check over the established shoulder or body side without reversing markings. | 4 / once | `look-behind` |
| `watching` | Track a slowly moving point while maintaining a steady body. | 4 / loop | `observing` |
| `attentive` | Lean subtly toward an interlocutor to show full attention. | 4 / loop | `attention-ready` |
| `standing` | Establish and sustain a balanced upright resting posture. | 4 / loop | — |
| `sitting` | Move down into a clearly seated posture. | 4 / once | — |
| `crouching` | Lower the center of mass while keeping support ready for movement. | 4 / once | `crouch` |
| `resting` | Recline into a supported recovery posture without falling asleep. | 4 / once | `rest` |
| `lounging` | Adopt a deliberately casual reclined pose with loose balance. | 4 / once | — |
| `leaning` | Shift into a stable body inclination without inventing a wall or support. | 4 / loop | — |
| `fidgeting` | Repeat a small restless body adjustment during stationary waiting. | 4 / loop | — |
| `swaying` | Move side to side around a fixed base in a soft repeating rhythm. | 4 / loop | — |
| `rocking` | Transfer weight forward and backward around a stable base. | 4 / loop | — |
| `stretching` | Lengthen the established body and joints before relaxing them. | 4 / once | `stretch` |
| `settling` | Make small final adjustments after a posture or action ends. | 4 / once | — |
| `waiting` | Ask patiently for approval, assistance or input. | 4 / loop | `needs-input`, `waiting-for-input` |
| `stillness` | A single intentional motionless neutral pose. | 1 / hold | `neutral-static` |
| `stoic-idle` | Preserve a composed nearly immovable personality with restrained breathing. | 4 / loop | — |
| `mischievous-idle` | Hint at a playful scheme through restrained asymmetric attention. | 4 / loop | — |
| `nervous-idle` | Sustain a timid baseline with small self-contained adjustments. | 4 / loop | — |
| `regal-idle` | Carry a dignified upright personality with deliberate tiny corrections. | 4 / loop | — |
| `bouncy-idle` | Express a buoyant personality with contained vertical springiness. | 4 / loop | — |
| `listening` | Attend to another speaker with receptive stillness and a small acknowledgment. | 4 / loop | `active-listening` |

## Positive Emotions (26)

Distinct favorable emotional reactions through timing, posture and approved expression.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `happy` | Show an openly cheerful overall emotional state. | 4 / once | `joyful`, `cheerful` |
| `smiling` | Form a slow visible smile without a whole-body celebration. | 4 / once | — |
| `laughing` | Laugh in several broad rhythmic body pulses. | 4 / once | `laughter` |
| `giggling` | Contain a small amused laugh with tucked shoulders or body. | 4 / once | — |
| `delighted` | React warmly to a pleasing small discovery. | 4 / once | — |
| `excited` | Build visible eager energy for something about to happen. | 4 / once | `enthusiastic` |
| `ecstatic` | Release unusually strong joyful emotion through a broad body opening. | 4 / once | — |
| `content` | Rest in satisfied ease after a need has been met. | 4 / loop | `satisfied` |
| `peaceful` | Settle attention inward with untroubled open body balance. | 4 / loop | `serene` |
| `proud` | Acknowledge an accomplishment with a lifted, composed posture. | 4 / once | — |
| `confident` | Display assurance before taking on a challenge. | 4 / once | — |
| `triumphant` | Claim a decisive win with a broad held victory posture. | 4 / once | `triumph` |
| `relieved` | Release tension when an anticipated difficulty has passed. | 4 / once | `relief` |
| `grateful` | Respond to kindness with a small sincere inward acknowledgment. | 4 / once | `thankful`, `gratitude` |
| `affectionate` | Lean warmly toward another presence without drawing a partner. | 4 / once | `loving`, `love` |
| `inspired` | Become newly energized by an idea or example. | 4 / once | — |
| `hopeful` | Look forward with cautious positive expectation. | 4 / once | `optimistic` |
| `amused` | Notice something funny with a restrained asymmetric response. | 4 / once | — |
| `playful` | Invite light play through a teasing forward-and-back body feint. | 4 / loop | — |
| `curious` | Become interested in an unfamiliar detail. | 4 / once | `curiosity` |
| `impressed` | Register admiration for an unexpected accomplishment. | 4 / once | — |
| `fascinated` | Sustain intense absorbed interest in a compelling detail. | 4 / loop | — |
| `positive-surprise` | React to an unexpected pleasant event with quick opening and warm recovery. | 4 / once | `pleasantly-surprised`, `surprised-positively` |
| `motivated` | Gather determination to begin purposeful effort. | 4 / once | `determined` |
| `encouraged` | Recover willingness after receiving reassurance. | 4 / once | — |
| `celebrating` | Perform a short repeated joyful victory rhythm. | 4 / once | `celebration`, `celebrate` |

## Negative and Difficult Emotions (30)

Non-graphic distress and difficult feelings with recoverable, readable body language.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `sad` | Settle into sustained low-energy sadness. | 4 / once | `sorrowful` |
| `crying` | Express restrained crying through face and shaking posture. | 4 / once | `weeping` |
| `disappointed` | React to an outcome falling short of expectation. | 4 / once | — |
| `discouraged` | Lose willingness after repeated unsuccessful effort. | 4 / once | — |
| `frustrated` | Show blocked effort with a tense repeated failed push. | 4 / once | `frustration` |
| `angry` | Express controlled strong anger through an anchored forceful pose. | 4 / once | `anger` |
| `annoyed` | React to a small irritation with a sharp restrained dismissal. | 4 / once | `irritated` |
| `grumpy` | Sustain a stubbornly displeased resting attitude. | 4 / loop | — |
| `worried` | Revisit an uncertain concern with inward guarded movement. | 4 / once | `concerned` |
| `anxious` | Express unsettled anticipation through tight small repeated adjustments. | 4 / once | `nervous` |
| `afraid` | Protect the body from a perceived threat. | 4 / once | `frightened`, `fearful` |
| `startled` | React abruptly to an unexpected cue and begin regaining balance. | 4 / once | `startle` |
| `panicked` | Lose calm through urgent disorganized but contained movement. | 4 / once | `panic` |
| `embarrassed` | Respond to unwanted attention with a small inward turn. | 4 / once | `embarrassment` |
| `shy` | Approach social contact cautiously from a protected posture. | 4 / once | `bashful` |
| `ashamed` | Turn inward after recognizing one's own mistake. | 4 / once | `shame` |
| `lonely` | Seek absent company with a slow outward look and dejected return. | 4 / once | — |
| `bored` | Show under-stimulated restlessness and low engagement. | 4 / loop | — |
| `overwhelmed` | Become unable to keep up with several implied demands. | 4 / once | `overloaded` |
| `confused` | Struggle to interpret an unclear cue through alternating orientation. | 4 / once | `confusion`, `puzzled` |
| `jealous` | Notice another's reward with conflicted inward and outward attention. | 4 / once | `envious` |
| `suspicious` | Inspect a questionable cue with guarded narrowed attention. | 4 / once | `distrustful` |
| `insecure` | Seek reassurance while doubting one's own readiness. | 4 / once | `uncertain-of-self` |
| `defeated` | Yield after effort with a clear loss of active resistance. | 4 / once | `defeat` |
| `regretful` | Reconsider a past action with a slow backward glance and lowered recovery. | 4 / once | `regret` |
| `exhausted` | Reach the limit of effort and sink into stable spent rest. | 4 / once | `spent` |
| `impatient` | Demand progress through a repeated tight timing gesture. | 4 / loop | — |
| `hesitant` | Begin an action, withdraw and pause before committing. | 4 / once | `hesitation` |
| `uncomfortable` | Reposition to reduce a mild physical or social discomfort. | 4 / once | `uneasy` |
| `distressed` | Ask for help from a visibly strained protective posture. | 4 / once | `distress` |

## Cognitive and Intellectual (29)

Observable thinking, inquiry, communication and learning performances.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `thinking` | Weigh an idea through a quiet inward pause and deliberate shift. | 4 / loop | `pondering`, `contemplating` |
| `reasoning` | Compare linked possibilities in a measured sequential rhythm. | 4 / loop | — |
| `brainstorming` | Explore several new possibilities with expanding attention. | 4 / loop | — |
| `concentrating` | Sustain effortful focus on one point while excluding distractions. | 4 / loop | `focused` |
| `analyzing` | Break a subject into parts through systematic alternating inspection. | 4 / loop | `analysis` |
| `questioning` | Ask for clarification with an open inquisitive body gesture. | 4 / loop | `asking-a-question` |
| `investigating` | Pursue a clue with a sequence of progressively closer examinations. | 4 / loop | `investigation` |
| `inspecting` | Check a single detail with controlled close attention. | 4 / loop | `inspect` |
| `scanning` | Sweep attention methodically across an implied area. | 4 / loop | `scan` |
| `searching` | Look among several possible locations for a missing target. | 4 / loop | `search` |
| `remembering` | Retrieve a memory through withdrawal, recognition and a softened return. | 4 / loop | `recall` |
| `realization` | Suddenly connect an explanation after a brief still pause. | 4 / loop | `realizing`, `aha` |
| `having-an-idea` | Propose a new approach with a rising anticipatory gesture. | 4 / loop | `idea`, `eureka` |
| `learning` | Alternate receiving information and trying a small new response. | 4 / loop | — |
| `studying` | Sustain careful deliberate attention to approved learning material. | 4 / loop | — |
| `reading` | Track across approved reading material with sequential head or eye motion. | 4 / loop | — |
| `writing` | Make controlled alternating strokes on approved writing material. | 4 / loop | — |
| `calculating` | Count or compare quantities through small evenly timed confirmations. | 4 / loop | — |
| `planning` | Arrange an intended sequence through distinct forward-directed beats. | 4 / loop | `plan` |
| `deciding` | Resolve a choice with a central pause and a committed turn. | 4 / loop | `choosing` |
| `evaluating` | Compare a candidate against a stable expectation. | 4 / loop | `assessing` |
| `understanding` | Receive an explanation and show gradual comprehension. | 4 / loop | `comprehending` |
| `explaining` | Present a point through one clear opening and supporting gesture. | 4 / loop | `responding` |
| `teaching` | Lead an explanation while checking the learner's response. | 4 / loop | `tutoring` |
| `speaking` | Show natural speech activity using the approved mouth. | 4 / loop | `talking`, `voice-activity` |
| `presenting` | Address an audience with a broad composed explanatory opening. | 4 / loop | `presentation` |
| `debating` | Respond to an opposing point with measured emphasis and a listening pause. | 4 / loop | — |
| `review` | Inspect completed output with deliberate evaluative attention. | 4 / loop | `reviewing`, `reviewing-output` |
| `problem-solving` | Test an approach, notice a mismatch and adjust the next attempt. | 4 / loop | `solving` |

## Movement and Locomotion (40)

Directional movement and whole-body physical transitions without implied mirroring.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `walking-right` | Walk toward the right through an alternating planted gait. | 4 / loop | `walk-right` |
| `walking-left` | Walk toward the left with independently drawn left-facing poses. | 4 / loop | `walk-left` |
| `walking-forward` | Walk toward the viewer with alternating front-view contacts. | 4 / loop | `walk-forward` |
| `walking-backward` | Retreat while maintaining a front-facing cautious gait. | 4 / loop | `walk-backward` |
| `walking-away` | Walk away from the viewer using the approved rear identity view. | 4 / loop | `walk-away` |
| `running-right` | Run right with an unmistakable alternating athletic stride. | 4 / loop | `run-right` |
| `running-left` | Run left with independently preserved left-side anatomy. | 4 / loop | `run-left` |
| `running-forward` | Run toward the viewer with front-facing alternating drive. | 4 / loop | `run-forward` |
| `running-away` | Run away using the approved rear-view character structure. | 4 / loop | `run-away` |
| `sprinting` | Show maximum-effort short fast strides in the approved direction. | 4 / loop | `sprint` |
| `jogging` | Sustain an easy athletic gait between walking and sprinting. | 4 / loop | `jog` |
| `tiptoeing` | Advance delicately on minimal approved foot contacts. | 4 / loop | `tiptoe` |
| `sneaking` | Move cautiously while keeping the body low and attentive. | 4 / loop | `sneak` |
| `hopping` | Repeat a compact two-beat rise from the established support anatomy. | 4 / once | `hop` |
| `skipping` | Alternate a step and buoyant hop in a playful gait. | 4 / loop | `skip` |
| `jumping` | Perform anticipation, lift, airborne peak and a controlled landing. | 4 / once | `jump` |
| `double-jumping` | Add a second deliberate body impulse while already airborne. | 4 / once | `double-jump` |
| `landing` | Absorb downward motion into a stable planted stance. | 4 / once | `land` |
| `bouncing` | Rebound elastically through a repeatable vertical compression cycle. | 4 / once | `bounce` |
| `dashing` | Make one explosive directional burst and begin controlled braking. | 4 / once | `dash` |
| `sliding` | Maintain a low gliding posture while indicating controlled lateral travel. | 4 / loop | `slide` |
| `crawling` | Move close to the ground with alternating approved contact points. | 4 / loop | `crawl` |
| `climbing` | Pull and push upward using approved grasping or climbing anatomy. | 4 / loop | `climb` |
| `swimming` | Propel the character through a smooth repeated aquatic body stroke. | 4 / loop | `swim` |
| `floating` | Drift gently without active propulsion in a stable suspended pose. | 4 / loop | `float` |
| `flying` | Use real approved wings through a lift-producing flap cycle. | 4 / loop | `fly` |
| `hovering` | Maintain a nearly fixed airborne position through small repeated wing strokes. | 4 / loop | `hover` |
| `gliding` | Hold approved wings extended while making small directional corrections. | 4 / loop | `glide` |
| `spinning` | Turn through a full approved character rotation at fixed scale. | 4 / loop | `spin` |
| `rolling` | Roll the body through a compact full-body rotation. | 4 / loop | `roll` |
| `turning-left` | Pivot the planted body toward the left. | 4 / once | `turn-left` |
| `turning-right` | Pivot the planted body toward the right. | 4 / once | `turn-right` |
| `falling` | Lose support and begin a controlled non-graphic downward fall. | 4 / once | `fall` |
| `stumbling` | Interrupt a gait with a brief uneven support correction. | 4 / once | `stumble` |
| `tripping` | Catch a support unexpectedly and pitch forward before bracing. | 4 / once | `trip` |
| `balance-recovery` | Regain balance from a visibly unstable tilted posture. | 4 / once | `recovering-balance`, `physical-recovery` |
| `approaching` | Move attention and body toward an interlocutor without scaling up. | 4 / once | `approach` |
| `retreating` | Withdraw cautiously from an implied source while remaining attentive. | 4 / once | `retreat` |
| `stopping` | Decelerate from motion into a balanced planted finish. | 4 / once | `stop-motion` |
| `changing-direction` | Brake and redirect the body toward the opposite travel side. | 4 / once | `change-direction` |

## Social Interactions and Gestures (32)

Interpersonal and nonverbal actions with anatomy and partner constraints.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `waving` | Greet through a friendly oscillation of one approved upper limb. | 4 / once | `wave` |
| `greeting` | Welcome someone through an open forward-facing body acknowledgment. | 4 / once | `hello`, `saying-hello` |
| `saying-goodbye` | Offer a gentle final farewell through a lingering backward-facing acknowledgment. | 4 / once | `goodbye` |
| `nodding` | Give a clear measured affirmative head movement. | 4 / once | `nod` |
| `shaking-head` | Refuse or disagree through a small lateral head movement. | 4 / once | `head-shake` |
| `bowing` | Offer respect with a deliberate forward bend and measured return. | 4 / once | `bow` |
| `saluting` | Raise an approved hand to a precise respectful salute. | 4 / once | `salute` |
| `clapping` | Applaud by visibly bringing paired approved hands together and apart. | 4 / loop | `applause`, `clap` |
| `high-fiving` | Offer a single raised-palm contact gesture toward an implied partner. | 4 / once | `high-five` |
| `hugging` | Offer an embrace toward an implied partner with established upper limbs. | 4 / once | `hug` |
| `pointing` | Direct attention with an approved hand or pointing appendage. | 4 / once | `point` |
| `beckoning` | Invite someone closer through a repeated inward upper-limb gesture. | 4 / once | `beckon` |
| `shrugging` | Show uncertainty or limited knowledge through a symmetric upper-body lift. | 4 / once | `shrug` |
| `thumbs-up` | Confirm approval with a stable raised approved thumb. | 4 / once | `thumbs-up-gesture` |
| `thumbs-down` | Signal disapproval with an intentional downward approved thumb. | 4 / once | `thumbs-down-gesture` |
| `facepalming` | Briefly cover the approved face with an approved palm after a mistake. | 4 / once | `facepalm` |
| `apologizing` | Offer a sincere subdued acknowledgment after a mistake. | 4 / once | `apologizing-gesture`, `sorry` |
| `thanking` | Make a deliberate courteous acknowledgment toward a helper. | 4 / once | `thanking-gesture`, `thank-you` |
| `requesting-attention` | Ask to be noticed with one modest lift and an expectant pause. | 4 / once | `attention-request` |
| `acknowledging` | Confirm receipt of a cue with a brief whole-body inclination. | 4 / once | `acknowledge`, `received` |
| `agreeing` | Align with another's proposal using an open affirmative lean. | 4 / once | `agree`, `yes` |
| `disagreeing` | State a difference through a controlled outward turn and closed pause. | 4 / once | `disagree`, `no` |
| `encouraging` | Urge another onward with a supportive forward pulse. | 4 / once | `encourage` |
| `consoling` | Offer comfort through a slow low-energy approach and gentle pause. | 4 / once | `comfort` |
| `sharing` | Offer part of an approved held resource without surrendering all of it. | 4 / once | — |
| `giving` | Hand an approved item toward an implied recipient. | 4 / once | `give` |
| `receiving` | Accept an approved item from an implied giver. | 4 / once | `receive` |
| `inviting` | Welcome participation with a broad open body turn. | 4 / once | `invite` |
| `cheering` | Encourage a performer with repeated upward rhythmic body accents. | 4 / loop | `cheer` |
| `posing` | Arrange the character into a deliberate portrait stance. | 4 / once | `pose` |
| `winking` | Close one approved eye while keeping the other attentive. | 4 / once | `wink` |
| `introducing` | Present oneself with a modest inward indication then an open welcome. | 4 / once | `introduce` |

## Daily Life and Creature Needs (49)

Daily routines, care and anatomy-specific creature performances.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `hungry` | Seek food through a low-energy forward sniff or expectant body gesture. | 4 / loop | `hunger` |
| `eating` | Consume approved food with changing attached jaw or feeding motions. | 4 / loop | `eat` |
| `drinking` | Take measured sips from an approved drinking source. | 4 / loop | `drink` |
| `thirsty` | Request a drink through a dry pause and expectant orientation. | 4 / loop | `thirst` |
| `yawning` | Open into a gradual large yawn and close with a relaxed recovery. | 4 / once | `yawn` |
| `sleeping` | Sustain a clearly asleep resting posture with slow breathing. | 4 / loop | `asleep`, `sleep` |
| `dreaming` | Remain asleep while making a brief contained dream twitch. | 4 / loop | `dream` |
| `waking` | Move from sleep into gradual alertness. | 4 / once | `waking-up`, `wake` |
| `energetic` | Show readiness for physical play through contained quick springiness. | 4 / loop | `full-energy` |
| `tired` | Wind down after activity with gradually heavier movement. | 4 / loop | `fatigued` |
| `sick` | Show mild non-graphic malaise through protective slow movement. | 4 / loop | `ill` |
| `healing` | Show gradual physical comfort returning during a calm recovery cycle. | 4 / loop | `recuperating` |
| `healthy` | Display comfortable balanced vitality after care. | 4 / loop | `well` |
| `dirty` | Notice and inspect an explicitly approved dirty appearance variant. | 4 / once | — |
| `bathing` | Clean the body using an explicitly approved washing implement. | 4 / loop | `washing` |
| `grooming` | Smooth an existing coat or surface with an approved grooming movement. | 4 / loop | `self-grooming` |
| `scratching` | Reach a real itchy spot with an anatomically possible limb. | 4 / loop | `scratch` |
| `sniffing` | Investigate a nearby scent with short forward nose or mouth movements. | 4 / loop | `sniff` |
| `exploring` | Investigate surroundings through alternating cautious advance and orientation. | 4 / loop | `explore` |
| `playing` | Engage in a self-contained friendly play feint. | 4 / loop | `play` |
| `exercising` | Repeat a balanced physical effort and controlled release. | 4 / loop | `exercise` |
| `meditating` | Sustain centered stillness with a slow deliberate breath. | 4 / loop | `meditation` |
| `relaxing` | Release activity-related tension progressively into comfort. | 4 / once | `relaxation` |
| `being-petted` | Respond warmly to implied gentle contact from outside the character artwork. | 4 / loop | `petted` |
| `seeking-attention` | Approach the viewer with a soft repeated request for companionship. | 4 / loop | `attention-seeking` |
| `hiding` | Withdraw into a smaller protected body silhouette without adding cover objects. | 4 / once | `hide` |
| `shivering` | Make small irregular cold-related body tremors around a tucked posture. | 4 / loop | `shiver` |
| `overheating` | Slow down and open posture to release heat without changing colors. | 4 / loop | `too-hot` |
| `cooling-down` | Return gradually to comfortable rhythm after heat or effort. | 4 / once | `cool-down` |
| `warming-up` | Restore comfortable movement after cold through small progressive motions. | 4 / once | `warm-up` |
| `tail-wagging` | Wag an approved tail from its anatomical root in a friendly rhythm. | 4 / loop | `wag-tail` |
| `ear-twitching` | Twitch one approved ear briefly toward a subtle cue. | 4 / once | `ear-twitch` |
| `wing-stretching` | Extend approved wings slowly to release tension without taking flight. | 4 / once | `stretch-wings` |
| `paw-grooming` | Clean an approved forepaw with attached mouth contact. | 4 / loop | `grooming-paw` |
| `curling-up` | Fold into a compact anatomically plausible resting curl. | 4 / once | `curl-up` |
| `purring` | Express content through a tiny relaxed throat and torso vibration. | 4 / loop | `purr` |
| `kneading` | Alternate pressure from two approved front paws in a contented rhythm. | 4 / loop | `making-biscuits` |
| `play-bowing` | Invite play by lowering the forequarters while keeping hindquarters raised. | 4 / once | — |
| `tail-tucking` | Draw an approved tail close under the body in a protective response. | 4 / once | `tuck-tail` |
| `ear-flattening` | Rotate approved ears backward in a cautious defensive response. | 4 / once | `flatten-ears` |
| `wing-fluttering` | Make a brief rapid small-range wing flutter while staying grounded. | 4 / once | `flutter-wings` |
| `preening` | Smooth approved feathers through careful beak-to-feather contact. | 4 / loop | — |
| `fin-fanning` | Open and close approved fins in a slow stationary display. | 4 / loop | `fan-fins` |
| `antenna-probing` | Explore nearby space with alternating approved antenna motions. | 4 / loop | — |
| `shell-retreating` | Withdraw anatomically supported soft parts into an approved shell. | 4 / once | `retract-into-shell` |
| `tentacle-waving` | Greet with a controlled ripple along one approved tentacle. | 4 / once | — |
| `slithering` | Propel a legless approved body through alternating continuous curves. | 4 / loop | `slither` |
| `fur-shaking` | Shake an approved fur coat through a brief torso-led oscillation. | 4 / once | `shake-coat` |
| `perching` | Settle a winged creature onto its own supported feet without drawing a branch. | 4 / once | — |

## AI Agent and Software Workflow (43)

Task lifecycle and software-work statuses; running means active processing.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `ready` | Signal available task readiness through a steady outward attentive stance. | 4 / loop | `available`, `awake` |
| `initializing` | Move from inactive compactness into gradually organized task readiness. | 4 / once | `booting` |
| `loading` | Sustain a restrained cyclic preparation motion while resources become available. | 4 / loop | `load` |
| `queued` | Wait in orderly low-energy readiness behind other work. | 4 / loop | `in-queue` |
| `preparing` | Arrange posture and approved task dependencies before work begins. | 4 / loop | `preparation` |
| `researching` | Alternate gathering attention across multiple implied information sources. | 4 / loop | `research` |
| `retrieving` | Reach attention toward an implied source and bring it back for use. | 4 / loop | `retrieval` |
| `running` | Actively process a task through focused non-locomotion work. | 4 / loop | `working`, `processing`, `active-task` |
| `generating` | Build toward a new result with a controlled expanding work gesture. | 4 / loop | `generation` |
| `coding` | Compose software through deliberate approved keyboard work and a brief reasoning pause. | 4 / loop | `programming` |
| `typing` | Perform a steady alternating keyboard input rhythm. | 4 / loop | `keyboard-input` |
| `building` | Assemble task output through distinct gather, fit and check body beats. | 4 / loop | `software-building` |
| `compiling` | Sustain a methodical processing cadence interrupted by short verification pauses. | 4 / loop | `compile` |
| `testing` | Probe an implied result, observe the response and reset for another check. | 4 / loop | `tests-running` |
| `debugging` | Reproduce a problem and inspect a specific mismatch before another attempt. | 4 / loop | `debug` |
| `validating` | Compare an implied candidate to a fixed requirement with a careful measured check. | 4 / loop | `validation` |
| `verifying` | Recheck an already evaluated result with an independent careful pass. | 4 / loop | `verification` |
| `saving` | Commit an implied result with a compact careful closing gesture. | 4 / once | `save` |
| `syncing` | Alternate attention between two implied endpoints in a balanced exchange. | 4 / loop | `synchronizing` |
| `uploading` | Direct controlled work attention from the character toward an external endpoint. | 4 / loop | `upload` |
| `downloading` | Bring controlled attention from an external endpoint toward the local task. | 4 / loop | `download` |
| `deploying` | Present a completed result outward with a deliberate final readiness check. | 4 / once | `deployment` |
| `completed` | Mark the end of work with a controlled release and final outward acknowledgment. | 4 / once | `complete`, `done` |
| `successful` | Acknowledge a confirmed successful result with a modest clear uplift. | 4 / once | `success`, `succeeded` |
| `partially-successful` | Acknowledge useful progress while retaining a visible unresolved reservation. | 4 / once | `partial-success` |
| `failed` | React to an unsuccessful task with deflation and recoverable attention. | 4 / once | `failure` |
| `warning` | Signal caution with a controlled alert posture and deliberate pause. | 4 / once | `caution` |
| `error` | Register a specific unexpected task fault with a brief checked recoil. | 4 / once | `fault` |
| `blocked` | Stop purposeful progress at a barrier and remain visibly unable to proceed. | 4 / loop | `blocker` |
| `waiting-for-approval` | Seek a decision before proceeding through a restrained outward offer. | 4 / loop | `approval-required` |
| `waiting-for-dependency` | Watch an unavailable prerequisite with patient task-oriented stillness. | 4 / loop | `dependency-wait` |
| `retrying` | Reset after an unsuccessful attempt and make one renewed deliberate effort. | 4 / loop | `retry` |
| `recovering` | Restore stable workflow after a disruption through measured reorganization. | 4 / once | `recovery`, `workflow-recovery` |
| `reconnecting` | Attempt to restore a lost connection through separated outward checks. | 4 / loop | `reconnect` |
| `offline` | Hold a subdued available-looking pose with attention withdrawn from external tasks. | 4 / loop | `disconnected` |
| `timed-out` | Stop an unanswered wait with a deliberate disappointed closure. | 4 / once | `timeout` |
| `rate-limited` | Suspend repeated attempts and settle into restrained paced waiting. | 4 / once | `throttled` |
| `paused` | Hold interrupted work in a stable suspended pose. | 4 / once | `pause` |
| `resumed` | Reengage a paused task with a small purposeful restarting movement. | 4 / once | `resume-work` |
| `cancelled` | Acknowledge deliberate task abandonment and return to availability. | 4 / once | `canceled`, `cancelled-work` |
| `interrupted` | Register a new demand that temporarily cuts across current work. | 4 / once | `interrupt-reaction` |
| `idle-timeout` | Let prolonged inactivity settle into a lower-energy passive pose. | 4 / once | `inactive` |
| `shutting-down` | Close activity deliberately and settle into an inactive final pose. | 4 / once | `shutdown` |

## Physical Activities and Hobbies (19)

Deliberate creative or practical work using only approved dependencies.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `dancing` | Perform a coordinated rhythmic whole-body dance phrase. | 4 / loop | `dance` |
| `singing` | Sustain expressive musical mouth shapes with measured breathing. | 4 / loop | `sing` |
| `playing-music` | Play an approved instrument with mechanically plausible attached movements. | 4 / loop | `playing-instrument` |
| `practicing` | Repeat a small skill movement while refining its control. | 4 / loop | — |
| `crafting` | Join approved craft material through a close precise hand action. | 4 / loop | `handcrafting` |
| `drawing` | Create a deliberate visual stroke on approved drawing material. | 4 / loop | `sketching` |
| `painting` | Apply a broad controlled brush movement to an approved surface. | 4 / loop | `paint` |
| `cooking` | Stir or prepare approved food with a consistent safe attached implement. | 4 / loop | — |
| `cleaning` | Make a repeated controlled wiping pass with an approved cleaning cloth. | 4 / loop | `wiping` |
| `organizing` | Sort approved items through a deliberate select-and-place rhythm. | 4 / loop | `tidying` |
| `gardening` | Tend an approved plant through a gentle controlled care action. | 4 / loop | — |
| `assembling` | Fit two approved physical components together with a precise alignment. | 4 / loop | `assembly` |
| `repairing` | Adjust a specific approved object fault with a precise tool action. | 4 / loop | `physical-repair` |
| `juggling` | Cycle approved juggling objects through explicitly reviewed in-slot trajectories. | 4 / loop | `juggle` |
| `throwing` | Throw one approved object through an explicit approved release sequence. | 4 / once | `throw` |
| `catching` | Receive an approved moving object with real contact and controlled deceleration. | 4 / once | `catch` |
| `kicking` | Kick an approved object with a controlled planted-support action. | 4 / once | `kick` |
| `balancing` | Maintain a challenging supported pose with small precise corrections. | 4 / loop | — |
| `performing` | Deliver a short deliberate audience-facing physical flourish. | 4 / loop | `performance` |

## Game and RPG (29)

Optional game character performances including non-graphic combat.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `ready-stance` | Hold a balanced game-action posture prepared for movement. | 4 / loop | `combat-ready`, `battle-ready` |
| `attacking` | Perform a controlled unarmed game strike toward an implied target. | 4 / once | `attack` |
| `defending` | Brace existing anatomy to protect against an implied incoming action. | 4 / once | `defend` |
| `dodging` | Shift quickly aside from an implied incoming strike. | 4 / once | `dodge` |
| `evading` | Withdraw through a longer controlled avoidance movement. | 4 / once | `evade` |
| `being-hit` | React non-graphically to an implied game impact with a compact recoil. | 4 / once | `hit-reaction`, `taking-hit` |
| `stunned` | Remain briefly disoriented after an implied game impact. | 4 / once | `stun` |
| `knocked-down` | Lose a guarded stance and settle into a safe prone game pose. | 4 / once | `knockdown` |
| `getting-up` | Return from a prone game pose to physical readiness. | 4 / once | `stand-up`, `knockdown-recovery` |
| `using-item` | Activate an approved game item through a clear held interaction. | 4 / once | `use-item` |
| `equipping` | Move an approved accessory from carried to its approved worn position. | 4 / once | `equip` |
| `unequipping` | Remove an approved accessory into its documented carried position. | 4 / once | `unequip` |
| `casting` | Perform an approved anatomy-only spellcasting gesture. | 4 / once | `spellcasting`, `cast` |
| `charging` | Gather effort in a compact held pose before a game action. | 4 / once | `charge` |
| `powering-up` | Build visible physical resolve through rising controlled posture. | 4 / once | `power-up` |
| `interacting` | Activate an implied nearby game interaction through an intentional body response. | 4 / once | `interact` |
| `collecting` | Acknowledge collecting an approved nearby game object. | 4 / once | `collect` |
| `picking-up` | Lift an approved object from a lower position into a stable hold. | 4 / once | `pickup`, `pick-up` |
| `dropping` | Release an approved held object into its approved lower destination. | 4 / once | `drop-item` |
| `gaining-experience` | Recognize incremental progress with a small earned confidence lift. | 4 / once | `gain-xp` |
| `victory` | End a game encounter with a composed decisive win pose. | 4 / once | `battle-victory` |
| `respawning` | Reestablish a game-ready pose after an approved inactive state. | 4 / once | `respawn` |
| `stealth` | Maintain a still compact concealed-ready game posture. | 4 / loop | `stealth-idle` |
| `discovery` | Register a newly found game location or object through attention and a pleased lift. | 4 / once | `discovering` |
| `alert` | Enter a heightened game patrol response after detecting a cue. | 4 / once | `alerted` |
| `pursuing` | Lean into sustained goal-directed locomotion toward an implied target. | 4 / loop | `chasing`, `pursuit` |
| `escaping` | Accelerate away from an implied threat while checking safe travel. | 4 / loop | `escape`, `fleeing` |
| `non-graphic-knockout` | Settle into a clearly inactive but non-graphic game defeat pose. | 4 / once | `knocked-out`, `ko` |
| `parrying` | Redirect an implied incoming game strike with one precise approved limb movement. | 4 / once | `parry` |

## Communication and Streaming (17)

Local browser mascot presentations and streaming reactions; no external platform integration claim.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `muted` | Indicate a speaking pause through a closed mouth and attentive held body. | 4 / once | `microphone-muted` |
| `unmuted` | Reopen availability to speak with a small preparatory breath. | 4 / once | `microphone-unmuted` |
| `reacting` | Offer a short audience-facing response to incoming conversation. | 4 / once | `live-reaction` |
| `incoming-message` | Notice a newly received message with a brief outward attention shift. | 4 / once | `message-received` |
| `notification` | Deliver one restrained notification gesture and return to calm. | 4 / once | `notify` |
| `audience-greeting` | Welcome a group with a broader inclusive attention sweep. | 4 / once | `stream-hello` |
| `answering-questions` | Listen briefly, form an answer and address the audience with measured emphasis. | 4 / once | `q-and-a` |
| `follower-celebration` | Acknowledge a small new audience milestone with a personal warm response. | 4 / once | `new-follower` |
| `milestone-celebration` | Celebrate a significant shared milestone with a larger sustained audience-facing pose. | 4 / once | `milestone` |
| `raid-reaction` | React to a sudden large audience arrival with surprise followed by inclusive welcome. | 4 / once | `raid` |
| `intermission` | Wind down performance and remain calmly present between segments. | 4 / loop | `break` |
| `starting-soon` | Build restrained expectant readiness before a presentation begins. | 4 / loop | `pre-show` |
| `be-right-back` | Signal a temporary absence with a brief reassuring departure acknowledgment. | 4 / once | `brb` |
| `stream-ending` | Offer a concluding audience acknowledgment and settle out of presentation mode. | 4 / once | `end-stream` |
| `buffering` | Suspend speech at a stable neutral mouth shape while a host resource is delayed. | 4 / loop | `buffer` |
| `connection-lost` | Notice a lost external link and turn from active performance into concerned waiting. | 4 / once | `stream-disconnected` |
| `returning-online` | Recover from disconnection and acknowledge restored audience contact. | 4 / once | `back-online` |

## Environmental Reactions (14)

Character-only responses to environmental cues, without painting those cues into character artwork.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `reacting-to-rain` | Respond to implied falling rain through a small protective posture. | 4 / once | `rain-reaction` |
| `reacting-to-snow` | Notice light implied snow with a curious upward pause. | 4 / once | `snow-reaction` |
| `reacting-to-wind` | Brace against an implied steady wind using body balance. | 4 / once | `wind-reaction` |
| `reacting-to-sunshine` | Relax into pleasant implied warmth with an open upward posture. | 4 / once | `sunshine-reaction` |
| `reacting-to-heat` | Notice sudden heat and pull back into a cautious open cooling posture. | 4 / once | `heat-reaction` |
| `reacting-to-cold` | React to a cold cue with a short contraction and protective tuck. | 4 / once | `cold-reaction` |
| `reacting-to-thunder` | Start at an implied thunderclap then check its source. | 4 / once | `thunder-reaction` |
| `reacting-to-darkness` | Become cautious as visibility is implied to decrease. | 4 / once | `darkness-reaction` |
| `reacting-to-bright-light` | Turn away from a sudden implied bright source while protecting existing eyes. | 4 / once | `bright-light-reaction` |
| `reacting-to-noise` | Locate an unexpected sound through an abrupt orientation followed by a check. | 4 / once | `noise-reaction` |
| `reacting-to-obstacle` | Stop before an implied obstacle and inspect a possible route around it. | 4 / once | `obstacle-reaction` |
| `reacting-to-confined-space` | Adjust approved anatomy into a compact careful passage posture. | 4 / once | `confined-space-reaction` |
| `reacting-to-sudden-change` | Reorient after an unexpected environmental change with a stabilizing check. | 4 / once | `environment-change` |
| `reacting-to-uneven-ground` | Adjust balance to an implied irregular surface through measured support shifts. | 4 / once | `terrain-reaction` |

## Narrative and Cinematic (13)

Story beats, character entrances and dramatic performances.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `introduction` | Reveal personality through a composed arrival posture and audience-facing flourish. | 4 / once | `character-introduction` |
| `anticipation` | Build visible preparation for an imminent story action. | 4 / once | `anticipating` |
| `suspense` | Sustain tense attention toward an unresolved offscreen possibility. | 4 / loop | `suspenseful-waiting` |
| `revelation` | Register a major new truth with widening posture and a slow changed recovery. | 4 / once | `revealed-truth` |
| `dramatic-reaction` | Deliver a pronounced but controlled whole-body response to a major story beat. | 4 / once | `drama` |
| `heroic-pose` | Establish a confident protective full-body silhouette. | 4 / once | `hero-pose` |
| `comedic-reaction` | Use a delayed double-take to communicate a humorous surprise. | 4 / once | `double-take` |
| `emotional-recovery` | Regain composure after an intense emotional moment. | 4 / once | `regaining-composure` |
| `farewell` | End a story relationship beat with a lingering warm turn away. | 4 / once | `narrative-farewell` |
| `entering` | Begin a scene through a contained arrival action within the character viewport. | 4 / once | `enter`, `transition-in` |
| `exiting` | Close scene participation through a deliberate turn and departure-ready pose. | 4 / once | `exit`, `transition-out` |
| `scene-resolution` | Release story tension and acknowledge a newly settled situation. | 4 / once | `resolution` |
| `finale` | Deliver a final emphatic audience-facing finish after a performance. | 4 / once | `grand-finale` |

## Transitions and Microexpressions (14)

Short connecting gestures and expression accents selected only when useful.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `eye-widening` | Briefly widen existing eyes at a small surprising detail. | 4 / once | `widen-eyes` |
| `squinting` | Narrow existing eyelids to inspect a difficult detail. | 4 / once | `squint` |
| `head-tilting` | Add a short inquisitive head angle without a full body turn. | 4 / once | `head-tilt` |
| `ear-perking` | Raise approved ears toward an attention cue. | 4 / once | `perk-ears` |
| `tail-twitching` | Make one brief localized movement at the tip of an approved tail. | 4 / once | `tail-twitch` |
| `brief-smile` | Add a quick small smile and return to neutral expression. | 4 / once | `smile-accent` |
| `brief-frown` | Add a short local frown at a minor concern. | 4 / once | `frown-accent` |
| `glancing` | Make one quick sideways attention check and return. | 4 / once | `glance` |
| `recoiling` | Pull the body a small distance away from an unexpected near cue. | 4 / once | `recoil` |
| `recoil-recovery` | Unfold from a compact recoil into ordinary stable attention. | 4 / once | — |
| `takeoff` | Transfer from a grounded winged posture into an approved airborne pose. | 4 / once | `taking-off` |
| `pose-transition` | Bridge between an approved neutral and an approved alternate resting posture. | 4 / once | `change-pose` |
| `return-to-idle` | Decay residual action into the approved neutral anchor. | 4 / once | `idle-recovery` |
| `mouth-close` | Close the approved mouth after speech without changing the rest of the face. | 4 / once | — |

## Lifecycle and Progression (14)

Identity-preserving progression cues; transformations require approved alternate identity.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `spawn` | Establish the approved character from a compact arrival-ready pose. | 4 / once | `spawning` |
| `emerge` | Unfold from a protected body posture into open environmental attention. | 4 / once | `emerging` |
| `hatch` | Emerge from an explicitly approved egg or enclosure into the approved young-character pose. | 4 / once | `hatching` |
| `grow` | Perform an approved progression gesture between explicitly documented age variants. | 4 / once | `growing` |
| `evolve` | Transition deliberately between explicitly approved evolutionary character forms. | 4 / once | `evolving` |
| `transform` | Move between two approved character forms through supplied intermediate poses. | 4 / once | `transforming` |
| `upgrade` | Acknowledge an approved capability improvement without altering the base silhouette. | 4 / once | `upgraded` |
| `leveling-up` | Celebrate a discrete earned progression level through one confident rise. | 4 / once | `level-up`, `leveling` |
| `adapting` | Adjust a familiar movement to a changed situation through a visible trial and correction. | 4 / once | `adapt` |
| `unlocking` | Recognize a newly available possibility with a cautious test then confident opening. | 4 / once | `unlock`, `unlock-ability` |
| `gaining-confidence` | Progress from guarded readiness into a steadier self-assured stance. | 4 / once | `gain-confidence` |
| `celebrating-achievement` | Honor the completion of a sustained personal effort with a proud calm acknowledgment. | 4 / once | `achievement` |
| `rest-after-effort` | Wind down an exertion into earned balanced rest. | 4 / once | `resting-after-effort` |
| `recover-from-setback` | Rebuild willingness after an unsuccessful attempt through a visible emotional reset. | 4 / once | `resilience`, `setback-recovery` |

## Accessibility and Special Purpose (13)

Low-motion and nonverbal status feedback with static alternatives.

| ID | Meaning | Frames / mode | Aliases |
| --- | --- | --- | --- |
| `low-stimulation-idle` | Sustain a very slow low-amplitude neutral presence. | 4 / loop | `reduced-motion-idle` |
| `static-neutral` | Provide one intentionally static balanced neutral pose. | 1 / hold | `static-idle` |
| `static-positive` | Provide one intentionally static positive expression and open posture. | 1 / hold | `positive-static` |
| `static-concern` | Provide one intentionally static restrained concern pose. | 1 / hold | `concern-static` |
| `static-working` | Provide one intentionally static focused task posture. | 1 / hold | `working-static` |
| `notification-safe` | Deliver a slow small notification acknowledgment with no repeated attention pulse. | 4 / once | `safe-notification` |
| `nonverbal-confirmation` | Confirm a choice with a small whole-body affirmative dip. | 4 / once | `confirmation`, `confirm` |
| `nonverbal-refusal` | Decline a choice through a restrained outward body turn and pause. | 4 / once | `refusal`, `decline` |
| `nonverbal-uncertainty` | Indicate insufficient certainty with a small open questioning tilt. | 4 / once | `uncertainty`, `unsure` |
| `assistance-needed` | Ask clearly for help using a slow readable open posture. | 4 / once | `help-needed`, `need-help` |
| `completion-acknowledgment` | Acknowledge finished work with a small calm outward inclination. | 4 / once | `completion-ack` |
| `attention-prompt` | Invite attention through a single slow deliberate body orientation. | 4 / once | `attention-cue` |
| `nonverbal-distress` | Signal sustained need for support in a stable readable body posture. | 4 / once | `accessible-distress` |

