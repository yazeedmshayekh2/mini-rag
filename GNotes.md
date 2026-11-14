# Stateless vs Stateful

**Stateless** means the server forgets you after each request. **Stateful** means the server remembers you between requests.

Think of ordering coffee:

- **Stateless:** Every time you walk up, you say your full order ("large latte, oat milk, name Yazeed"). The barista remembers nothing about your last visit, so any barista can serve you.
- **Stateful:** The barista knows you and says "the usual?" That's faster, but it has to be the same barista, and if they leave, the memory is gone.

In software terms:

- A stateless app, like a typical REST API, needs each request to carry everything required to handle it, such as an auth token and the data. This makes it easy to scale, because you can add more servers behind a load balancer and any of them can respond.
- A stateful app keeps data on the server between requests, such as a login session or shopping cart. This is convenient, but scaling is harder because the user has to keep reaching the same server, or the state has to be shared across servers.

A common design is to keep the app servers stateless and move the state into a database or a cache like Redis. You get the scaling benefits and still keep your data.