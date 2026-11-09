# LinkedIn launch post (draft)

> Draft for the author to edit and post. Every number comes from `docs/trials/T1-allocation.md`.

---

I model credit risk for a living. For the last few weeks I have been applying the same habit to robot fleets: don't believe a number until you have tried to break it.

fleetsim is an open-source lab for warehouse robot fleets: who fetches which shelf, how a hundred robots share narrow aisles without colliding, and what happens when batteries run low and parts fail.

The first result surprised me. The textbook-optimal assignment method (Hungarian) beat simple first-come-first-served dispatch by about 15%. Before celebrating, I wrote down a hypothesis and a pass bar, then ran 300 simulations. A one-line "closest pair first" rule matched it, at 100.5–101% of its throughput. The gain came from which orders get served first, not from optimal matching. One of my three predictions failed, and it's in the write-up.

You can start with one robot in the browser and grow a fleet from there: https://zakcination.github.io/fleetsim/academy.html

Code, trials and a learning path for people coming from analytics: https://github.com/zakcination/fleetsim

Built with AI coding agents; the experiment design and the verification are the parts I care about most.

#robotics #operationsresearch #simulation #analytics #opensource
