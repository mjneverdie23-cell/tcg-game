# Playing Primordia against another person

Two people, two computers, one match. Both need the same build — unzip it,
open `godot/project.godot` in **Godot 4.7**, press **Play**, and follow this.

## In the game

1. Both of you: **Collection** → make sure you have a legal deck saved.
2. Both of you: **Battle** tab → set the mode dropdown to
   **Versus player — over the network**. The big button becomes
   **FIND OPPONENT**. Press it.
3. **One of you hosts.** Pick your deck, press **Host a match**. The screen
   prints an address. Read it out to the other player.
4. **The other joins.** Pick your deck, type the address into the box,
   press **Join**.

That is the whole handshake. The coin toss appears on both screens and the
match begins.

## Which address to read out

The host's screen prints one of two things, and says which it is:

- **`203.0.113.42 (over the internet)`** — your router accepted the port
  forward the game asked for, and anyone anywhere can reach you. Read out
  the whole number.
- **`192.168.1.23 (same network only)`** — the router did not answer, so
  this address only works for someone on your Wi-Fi or in the same house.

If you need the internet address and only got the local one, see
*When it will not connect* below.

You can also type an address with a port on it — `203.0.113.42:24567` —
if your router forwards a different port to this machine.

## When it will not connect

The guest waits twelve seconds and then says so. Work down this list:

1. **Same house?** Use the `192.168.…` address. Nothing else needs doing.
2. **Different houses, and the host got the internet address?** It should
   just work. If it does not, the host's firewall is the usual culprit:
   allow Godot (or the exported game) to accept incoming connections.
3. **Different houses, and the host only got the local address?** The
   router refused to forward the port. Either:
   - turn on **UPnP** in the router's settings and host again, or
   - forward **UDP port 24567** to the host's computer by hand, then read
     out the host's public address (search "what is my IP"), or
   - put both machines on the same virtual network with something like
     Tailscale or ZeroTier, and use the address that gives you — from the
     game's point of view that is just the "same house" case.

The host's port mapping is removed again when they leave the lobby.

## What travels over the wire

Nothing about the board. Both machines build the identical battle from the
two decks and a shared random seed at the start, then exchange only the
moves each player makes. Every move carries a checksum of the state it
produced; if the two games ever disagree, the match stops immediately and
both sides are told, rather than drifting into two different games.

Arriving moves are checked against the rules before they are applied, so a
modified build cannot play a card it does not hold or act out of turn, and
the host checks the guest's deck is legal before the match starts.

**But**: each side runs a full copy of the engine, which includes the
opponent's hand and deck order. A modified build could read it. There is no
server refereeing this — play with people you would happily play across a
table.

## Odds and ends

- Online matches pay the usual coins for a win or a loss, and count toward
  your battle record, but **stake no trophies**. The ladder is a solo thing;
  an unrefereed link is not something to rank people on.
- Leaving the battle screen ends the match. The other player is told.
- If your opponent's game closes mid-match, you get "Match ended — your
  opponent disconnected". Nothing is paid out either way: nobody finished.
- Only one match per copy of the game at a time.
