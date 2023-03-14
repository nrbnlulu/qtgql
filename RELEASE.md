Release type: minor

This release adds initial support for mutations.

- [ ] Mutation handler (on par with query handler).
- [ ] commit slot.
- [ ] Support variables
- [ ] variables of Object / Enum / Scalars
- [ ] Should have a `property` for `operationOnFlight` (maybe queries as well)
- [ ] Mutations (or subscriptions) that return an iterable can accept an id for that iterator (currently `QGraphQLListModel`)
and when the data arrives it would update it.


This release also made `BaseQueryHandler` not a singleton, because you could have different
filters (on different handlers). Instead of `UseQuery{operationName: '...'}`
there would be `Require<operationName>{}` QQuickItem that would internally use
the generated <operationName> handler.
