## General observations
- CC still needs babysitting, so just running everything w/o human supervision is dangerous (but that is something we can maybe address)
- CC suggested already to extract a lesson

## Learnings from CC feature
- CC executes and waits for task output. can we add a hook and trigger it?
- uv run ao-tool record -c "print(2)"? Does this work?
- Generating valid JSON only in CLI for CC is hard. It wrote the JSON to a .txt and fed that into the command and it worked
    - CC is good at writing stuff to a file.. it leveraged that automatically
    - CC made a mistake with the required structure of the JSON it can change. We should flatten the dict so that there is only one level.
~~- Usercode can have internal caching (BEAVER). That messed up the edit-and-rerun command. AO needs to tell that CC so that CC first scans for that (otherwise could be hard to debug)~~
~~- ao-tool record can return the graph topology directly. Saves an extra call to ao-tool probe --topology~~
~~- ao-tool probe: should be able to access: output/input, and specific keys using regexes.~~
    ~~- --preview could return structure of flattened I/O dict~~
~~- human readable output probably better~~