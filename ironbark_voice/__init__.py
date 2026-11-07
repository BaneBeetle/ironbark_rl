"""IronBark voice: the robot speaks its "thoughts" aloud.

Pipeline (PC side): robot state -> triggers -> speech policy -> line (cache or Haiku)
-> ElevenLabs streaming TTS -> speaker. Read-only on the robot: nothing here publishes
motion commands (PC :5556), so this package can never move the dog.

Design calls are Brian's (docs/voice/decisions.md); Claude writes the code.
"""
