# QtGQL

![Logo](./assets/logo.svg){ align=center width=350}
*GraphQL client for Qt and QML.*
This library is an attempt to provide a high-level graphql client to the QT world.
## Similar projects
- [react-relay](https://relay.dev/)
- [apollo-client](https://www.apollographql.com/docs/react/)

## Features
!!! success "[Codegen (introspection compiler)](./codegen/tutorial.md)"
    - [x] Object types, for each field there is a corresponding `Property`
    - [x] Enums
    - [x] Custom scalars
    - [x] Unions
    - [x] Query handlers: queries your server when a component uses this query (or imperatively fetched).
    - [x] Query updates: fetch the same query multiple times would not instantiate everything from scratch
!!! success "Network layer"
    - [x] "Qt-native" graphql-transport-ws network manager (supports subscriptions).

!!! success "Helpers"
    - [x] [generic models](helpers/itemsystem.md) that get created from dictionaries (with update, pop, insert implemented by default)
    - [x] [`Property` classes](helpers/utilities.md#auto-property) that are accessible from QML, with dataclasses  syntax (using attrs)
    - [x] [`@slot`](helpers/utilities/#slot) - decorator to be replaced with `QtCore.Slot()` that get types from type hints.

## Installation

<div class="termy">

```console

// This would install our codegen dependencies as well...

$ pip install qtgql[codegen]

---> 100%
```

</div>
