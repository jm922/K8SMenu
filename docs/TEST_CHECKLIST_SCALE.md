# TEST_CHECKLIST_SCALE

## Purpose

This document is used to test and validate the **Scale Deployment** feature in the Kubernetes Resource Manager Deployment module.

The purpose of this checklist is to verify that the scale workflow works correctly, clearly, and safely in normal, edge, and failure scenarios.

---

## Feature Under Test

Menu path:

```text
Deployment -> Scale Deployment
```

Expected high-level behavior:

1. List available Deployments
2. Select a Deployment by number or name
3. Read and display the current replica count
4. Accept a new replica count
5. Show the exact `kubectl scale` command before execution
6. Ask for user confirmation
7. Execute the scale command
8. Show kubectl output
9. Re-fetch and display current Deployment replica status

---

## Recommended Test Deployment

Recommended Deployment name for testing:

```text
quicktest-web
```

Recommended reasons:

- already exists in the current test flow
- simple nginx workload
- easy to scale up and down
- Pod count changes are easy to observe

---

## Environment Baseline Check

### Objective
Make sure the cluster and Deployment environment are healthy enough to run scale tests.

### Steps
- [ ] Run `kubectl get nodes`
- [ ] Run `kubectl get deployment`
- [ ] Confirm at least one Deployment exists
- [ ] Confirm the target Deployment is accessible

### Reference Commands

```bash
kubectl get nodes
kubectl get deployment
kubectl get deployment quicktest-web
```

### Expected Result
- [ ] `kubectl` works normally
- [ ] nodes are in `Ready` state
- [ ] target Deployment exists
- [ ] no obvious cluster-side failure blocks testing

### Result Notes
- Result:
- Notes:

---

## Test Case 01 - Scale Up by Name

### Objective
Verify scale works correctly when increasing replicas using deployment name.

### Preconditions
- [ ] Cluster is healthy
- [ ] Deployment `quicktest-web` exists
- [ ] Deployment currently has fewer replicas than target

### Steps
- [ ] Open `Deployment -> Scale Deployment`
- [ ] Enter deployment name: `quicktest-web`
- [ ] Enter new replica count: `3`
- [ ] Confirm execution with `y`

### Expected Result
- [ ] Current replica count is shown before input
- [ ] Full kubectl command is displayed before execution
- [ ] The command is shown as:
  ```bash
  kubectl scale deployment quicktest-web --replicas=3
  ```
- [ ] Scale command executes successfully
- [ ] Success message is displayed
- [ ] Updated Deployment status summary is displayed
- [ ] Desired replicas becomes `3`

### Reference Commands

```bash
kubectl scale deployment quicktest-web --replicas=3
kubectl get deployment quicktest-web
kubectl get pods -l app=quicktest-web -o wide
```

### Result Notes
- Result:
- Notes:

---

## Test Case 02 - Scale Down by Name

### Objective
Verify scale works correctly when decreasing replicas using deployment name.

### Preconditions
- [ ] Deployment `quicktest-web` exists
- [ ] Deployment currently has more replicas than target

### Steps
- [ ] Open `Deployment -> Scale Deployment`
- [ ] Enter deployment name: `quicktest-web`
- [ ] Enter new replica count: `1`
- [ ] Confirm execution with `y`

### Expected Result
- [ ] Current replica count is shown before input
- [ ] Full kubectl command is displayed before execution
- [ ] The command is shown as:
  ```bash
  kubectl scale deployment quicktest-web --replicas=1
  ```
- [ ] Scale command executes successfully
- [ ] Success message is displayed
- [ ] Updated Deployment status summary is displayed
- [ ] Desired replicas becomes `1`

### Reference Commands

```bash
kubectl scale deployment quicktest-web --replicas=1
kubectl get deployment quicktest-web
kubectl get pods -l app=quicktest-web -o wide
```

### Result Notes
- Result:
- Notes:

---

## Test Case 03 - Scale by Number

### Objective
Verify scale works correctly when a Deployment is selected by menu number.

### Preconditions
- [ ] At least one Deployment exists in the current namespace

### Steps
- [ ] Open `Deployment -> Scale Deployment`
- [ ] Enter the deployment number shown in the menu list
- [ ] Enter a valid new replica count
- [ ] Confirm execution with `y`

### Expected Result
- [ ] Deployment number is resolved correctly
- [ ] No `Deployment not found` error
- [ ] Scale command runs successfully
- [ ] Deployment status summary is displayed

### Reference Commands

```bash
kubectl get deployment
kubectl scale deployment quicktest-web --replicas=2
```

### Result Notes
- Result:
- Notes:

---

## Test Case 04 - Scale to Same Replica Count

### Objective
Verify the program handles unchanged replica count correctly.

### Preconditions
- [ ] A valid Deployment exists
- [ ] Current replica count is known

### Steps
- [ ] Open `Deployment -> Scale Deployment`
- [ ] Select a valid Deployment
- [ ] Enter the same replica count as the current value

### Expected Result
- [ ] Program prints a message similar to:
  - `Replica count is already X. No changes applied.`
- [ ] No kubectl scale command is executed
- [ ] No traceback occurs

### Result Notes
- Result:
- Notes:

---

## Test Case 05 - Cancel Flow

### Objective
Verify that the scale operation can be cancelled before execution.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Open `Deployment -> Scale Deployment`
- [ ] Select a valid Deployment
- [ ] Enter a valid new replica count
- [ ] At the confirmation prompt, enter `n`

### Expected Result
- [ ] Full kubectl command is displayed before cancellation
- [ ] A cancel message is displayed
- [ ] No scale command is executed
- [ ] No traceback occurs
- [ ] Program returns safely to the menu flow

### Reference Command

```bash
# No kubectl scale command should actually be executed in this test
```

### Result Notes
- Result:
- Notes:

---

## Test Case 06 - Non-Existent Deployment by Name

### Objective
Verify that an invalid Deployment name is handled clearly and safely.

### Preconditions
- [ ] Scale Deployment menu is reachable

### Steps
- [ ] Open `Deployment -> Scale Deployment`
- [ ] Enter deployment name: `not-exist-deployment`

### Expected Result
- [ ] `Deployment not found` is displayed
- [ ] No scale command is executed
- [ ] No traceback occurs
- [ ] Program returns safely

### Result Notes
- Result:
- Notes:

---

## Test Case 07 - Invalid Deployment Number

### Objective
Verify that an invalid deployment number is handled correctly.

### Preconditions
- [ ] There is at least one Deployment in the menu list

### Steps
- [ ] Open `Deployment -> Scale Deployment`
- [ ] Enter an invalid number such as `99`

### Expected Result
- [ ] `Deployment not found` is displayed
- [ ] No scale command is executed
- [ ] No traceback occurs
- [ ] Program returns safely

### Result Notes
- Result:
- Notes:

---

## Test Case 08 - Invalid Replica Input (Non-Integer)

### Objective
Verify invalid non-integer replica input is rejected.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Open `Deployment -> Scale Deployment`
- [ ] Select a valid Deployment
- [ ] Enter new replica count: `abc`

### Expected Result
- [ ] Program prints a clear validation message
- [ ] No scale command is executed
- [ ] No traceback occurs

### Result Notes
- Result:
- Notes:

---

## Test Case 09 - Invalid Replica Input (Negative Number)

### Objective
Verify negative replica values are rejected.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Open `Deployment -> Scale Deployment`
- [ ] Select a valid Deployment
- [ ] Enter new replica count: `-1`

### Expected Result
- [ ] Program prints a clear validation message
- [ ] No scale command is executed
- [ ] No traceback occurs

### Result Notes
- Result:
- Notes:

---

## Test Case 10 - Scale to Zero

### Objective
Verify that scaling to zero is supported and handled correctly.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Open `Deployment -> Scale Deployment`
- [ ] Select a valid Deployment
- [ ] Enter new replica count: `0`
- [ ] Confirm execution with `y`

### Expected Result
- [ ] The full kubectl command is displayed
- [ ] Scale command executes successfully
- [ ] Deployment desired replicas becomes `0`
- [ ] Pods are eventually terminated
- [ ] No traceback occurs

### Reference Commands

```bash
kubectl scale deployment quicktest-web --replicas=0
kubectl get deployment quicktest-web
kubectl get pods -l app=quicktest-web -o wide
```

### Result Notes
- Result:
- Notes:

---

## Test Case 11 - Command Preview Accuracy

### Objective
Verify the displayed kubectl command exactly matches the intended command.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Run `Deployment -> Scale Deployment`
- [ ] Record the previewed kubectl command
- [ ] Manually run the same command in terminal
- [ ] Compare outputs

### Expected Result
- [ ] Command preview is accurate
- [ ] Manual command output matches menu command output
- [ ] No mismatch between displayed command and executed behavior

### Reference Commands

```bash
kubectl scale deployment quicktest-web --replicas=2
```

### Result Notes
- Result:
- Notes:

---

## Test Case 12 - Updated Status Accuracy

### Objective
Verify that the post-scale Deployment status summary is correct.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Run a successful scale operation
- [ ] Compare the status summary shown in the program with actual kubectl output

### Expected Result
- [ ] Desired replicas matches `kubectl get deployment`
- [ ] Updated replicas matches current rollout state
- [ ] Ready replicas matches current rollout state
- [ ] Available replicas matches current rollout state

### Reference Commands

```bash
kubectl get deployment quicktest-web
kubectl describe deployment quicktest-web
```

### Result Notes
- Result:
- Notes:

---

## Test Case 13 - Output Readability

### Objective
Verify that the scale output formatting is easy to read.

### Preconditions
- [ ] Scale Deployment feature works at least in one successful scenario

### Steps
- [ ] Run one successful scale test
- [ ] Review the output carefully

### Expected Result
- [ ] Title is clearly separated
- [ ] Deployment name is easy to identify
- [ ] Current replicas is clearly shown
- [ ] Target replicas is clearly shown
- [ ] kubectl command is displayed on its own line
- [ ] Success output is visually easy to notice
- [ ] Failure output is visually easy to notice
- [ ] Updated Deployment status summary is readable
- [ ] Line breaks and spacing are reasonable

### Result Notes
- Result:
- Notes:

---

## Test Case 14 - Empty Deployment List

### Objective
Verify the feature behaves safely when no Deployment exists.

### Preconditions
- [ ] Current namespace has no Deployment

### Steps
- [ ] Open `Deployment -> Scale Deployment`

### Expected Result
- [ ] `No deployments available` is shown
- [ ] No traceback occurs
- [ ] Program returns safely

### Reference Commands

```bash
kubectl get deployment
```

### Result Notes
- Result:
- Notes:

---

## Test Case 15 - Repeated Scale Operations

### Objective
Verify the feature works repeatedly without inconsistent behavior.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Scale the same Deployment multiple times in sequence
- [ ] Example: `1 -> 3 -> 2 -> 1`
- [ ] Observe behavior and output each time

### Expected Result
- [ ] No crash occurs
- [ ] No inconsistent output appears
- [ ] Command preview remains correct every time
- [ ] Deployment state follows requested values correctly

### Result Notes
- Result:
- Notes:

---

## Test Case 16 - Scale Up Then Verify Pod Count

### Objective
Verify that Pod count eventually matches the requested replica count after scale up.

### Preconditions
- [ ] A valid Deployment exists

### Steps
- [ ] Scale the Deployment from `1` to `3`
- [ ] Wait for the rollout to finish or observe pod creation
- [ ] Run `kubectl get pods -l app=<deployment-name>`

### Expected Result
- [ ] Pod count eventually equals desired replicas
- [ ] Pods become `Running`
- [ ] Deployment becomes healthy

### Reference Commands

```bash
kubectl scale deployment quicktest-web --replicas=3
kubectl get pods -l app=quicktest-web -o wide
kubectl get deployment quicktest-web
```

### Result Notes
- Result:
- Notes:

---

## Test Case 17 - Scale Down Then Verify Pod Count

### Objective
Verify that Pod count eventually matches the requested replica count after scale down.

### Preconditions
- [ ] A valid Deployment exists
- [ ] Deployment currently has multiple replicas

### Steps
- [ ] Scale the Deployment from `3` to `1`
- [ ] Wait for the scale-down process to complete
- [ ] Run `kubectl get pods -l app=<deployment-name>`

### Expected Result
- [ ] Pod count eventually equals desired replicas
- [ ] Remaining Pod is healthy
- [ ] Deployment becomes healthy

### Reference Commands

```bash
kubectl scale deployment quicktest-web --replicas=1
kubectl get pods -l app=quicktest-web -o wide
kubectl get deployment quicktest-web
```

### Result Notes
- Result:
- Notes:

---

## Minimal Regression Checklist

Use this short section after any future change to scale-related code.

- [ ] Scale up by deployment name
- [ ] Scale down by deployment name
- [ ] Scale by deployment number
- [ ] Scale to same value
- [ ] Cancel flow
- [ ] Invalid non-integer replica input
- [ ] Invalid negative replica input
- [ ] Scale to zero
- [ ] Command preview accuracy
- [ ] Output readability

---

## Final Summary

### Overall Status
- [ ] All required scale tests passed
- [ ] Feature is ready for regular use
- [ ] Follow-up improvements are still needed

### Known Follow-Up Improvements
- [ ] Add shortcut to rollout status after scale
- [ ] Add namespace support
- [ ] Improve input validation messaging
- [ ] Improve rollout-aware post-scale guidance
- [ ] Add batch scale support
- [ ] Add HPA-aware scale warning in the future

---

## Usage Notes

Recommended workflow:

1. Run one test case
2. Mark completed checkboxes with `- [x]`
3. Record the result in the `Result Notes` section
4. Keep this file updated as the feature evolves

Example:

```md
- [x] Scale up by deployment name
```

Example result note:

```md
### Result Notes
- Result: Passed
- Notes: Command preview matched manual kubectl scale execution and the Deployment scaled successfully.
```
